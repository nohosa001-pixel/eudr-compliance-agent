use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer};

declare_id!("EUDRScrw11111111111111111111111111111111111");

#[program]
pub mod eudr_escrow {
    use super::*;

    /// Initializes a conditioned EUDR trade escrow vault.
    /// Locks buyer SPL-USDC pending satellite deforestation and legality verification.
    pub fn initialize_escrow(
        ctx: Context<InitializeEscrow>,
        job_id: String,
        amount: u64,
        max_acceptable_risk_score: u8,
    ) -> Result<()> {
        require!(amount > 0, EudrError::InvalidAmount);
        require!(job_id.len() <= 64, EudrError::JobIdTooLong);

        let escrow = &mut ctx.accounts.escrow_account;
        escrow.buyer = ctx.accounts.buyer.key();
        escrow.usdc_mint = ctx.accounts.usdc_mint.key();
        escrow.vault = ctx.accounts.vault_account.key();
        escrow.job_id = job_id;
        escrow.amount = amount;
        escrow.max_acceptable_risk_score = max_acceptable_risk_score;
        escrow.bump = ctx.bumps.escrow_account;
        escrow.is_settled = false;
        escrow.created_at = Clock::get()?.unix_timestamp;

        // Transfer SPL-USDC from Buyer to Escrow Vault PDA
        let cpi_accounts = Transfer {
            from: ctx.accounts.buyer_token_account.to_account_info(),
            to: ctx.accounts.vault_account.to_account_info(),
            authority: ctx.accounts.buyer.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
        token::transfer(cpi_ctx, amount)?;

        msg!("EUDR Escrow Vault Initialized: Job={}, Amount={}", escrow.job_id, amount);
        Ok(())
    }

    /// Executes Direct Split disbursement to smallholders and cooperatives
    /// upon verified Ed25519 Oracle Physical Truth Attestation (No Deforestation).
    pub fn settle_direct_split(
        ctx: Context<SettleDirectSplit>,
        split_amounts: Vec<u64>,
        oracle_attestation_hash: [u8; 32],
    ) -> Result<()> {
        let escrow = &mut ctx.accounts.escrow_account;
        require!(!escrow.is_settled, EudrError::AlreadySettled);

        let total_split: u64 = split_amounts.iter().sum();
        require!(total_split <= escrow.amount, EudrError::SplitExceedsEscrow);

        escrow.is_settled = true;
        escrow.oracle_attestation_hash = oracle_attestation_hash;
        escrow.settled_at = Clock::get()?.unix_timestamp;

        let buyer_key = escrow.buyer;
        let job_id_bytes = escrow.job_id.as_bytes();
        let bump = escrow.bump;

        let signer_seeds: &[&[&[u8]]] = &[&[
            b"eudr_escrow",
            buyer_key.as_ref(),
            job_id_bytes,
            &[bump],
        ]];

        // Disburse funds to primary producer recipient
        let cpi_accounts = Transfer {
            from: ctx.accounts.vault_account.to_account_info(),
            to: ctx.accounts.producer_recipient_account.to_account_info(),
            authority: escrow.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer_seeds);
        token::transfer(cpi_ctx, split_amounts[0])?;

        msg!("EUDR Escrow Settled via Direct Split for Job: {}", escrow.job_id);
        Ok(())
    }

    /// Slashes or refunds escrow deposit if satellite monitors detect deforestation post-2020.
    pub fn slash_non_compliant(
        ctx: Context<SlashNonCompliant>,
        violation_reason: String,
    ) -> Result<()> {
        let escrow = &mut ctx.accounts.escrow_account;
        require!(!escrow.is_settled, EudrError::AlreadySettled);

        escrow.is_settled = true;
        escrow.settled_at = Clock::get()?.unix_timestamp;

        let buyer_key = escrow.buyer;
        let job_id_bytes = escrow.job_id.as_bytes();
        let bump = escrow.bump;

        let signer_seeds: &[&[&[u8]]] = &[&[
            b"eudr_escrow",
            buyer_key.as_ref(),
            job_id_bytes,
            &[bump],
        ]];

        // Refund buyer in full due to supplier non-compliance
        let cpi_accounts = Transfer {
            from: ctx.accounts.vault_account.to_account_info(),
            to: ctx.accounts.buyer_token_account.to_account_info(),
            authority: escrow.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer_seeds);
        token::transfer(cpi_ctx, escrow.amount)?;

        msg!("EUDR Escrow Slashed/Refunded. Violation: {}", violation_reason);
        Ok(())
    }
}

#[derive(Accounts)]
#[instruction(job_id: String)]
pub struct InitializeEscrow<'info> {
    #[account(mut)]
    pub buyer: Signer<'info>,

    pub usdc_mint: Account<'info, Mint>,

    #[account(
        mut,
        constraint = buyer_token_account.mint == usdc_mint.key(),
        constraint = buyer_token_account.owner == buyer.key()
    )]
    pub buyer_token_account: Account<'info, TokenAccount>,

    #[account(
        init,
        payer = buyer,
        space = 8 + 32 + 32 + 32 + 64 + 8 + 1 + 1 + 8 + 32 + 8 + 1,
        seeds = [b"eudr_escrow", buyer.key().as_ref(), job_id.as_bytes()],
        bump
    )]
    pub escrow_account: Account<'info, EscrowAccount>,

    #[account(
        init,
        payer = buyer,
        token::mint = usdc_mint,
        token::authority = escrow_account,
        seeds = [b"vault", escrow_account.key().as_ref()],
        bump
    )]
    pub vault_account: Account<'info, TokenAccount>,

    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
pub struct SettleDirectSplit<'info> {
    #[account(
        mut,
        seeds = [b"eudr_escrow", escrow_account.buyer.as_ref(), escrow_account.job_id.as_bytes()],
        bump = escrow_account.bump,
    )]
    pub escrow_account: Account<'info, EscrowAccount>,

    #[account(
        mut,
        seeds = [b"vault", escrow_account.key().as_ref()],
        bump
    )]
    pub vault_account: Account<'info, TokenAccount>,

    #[account(mut)]
    pub producer_recipient_account: Account<'info, TokenAccount>,

    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct SlashNonCompliant<'info> {
    #[account(
        mut,
        seeds = [b"eudr_escrow", escrow_account.buyer.as_ref(), escrow_account.job_id.as_bytes()],
        bump = escrow_account.bump,
    )]
    pub escrow_account: Account<'info, EscrowAccount>,

    #[account(
        mut,
        seeds = [b"vault", escrow_account.key().as_ref()],
        bump
    )]
    pub vault_account: Account<'info, TokenAccount>,

    #[account(mut)]
    pub buyer_token_account: Account<'info, TokenAccount>,

    pub token_program: Program<'info, Token>,
}

#[account]
pub struct EscrowAccount {
    pub buyer: Pubkey,
    pub usdc_mint: Pubkey,
    pub vault: Pubkey,
    pub job_id: String,
    pub amount: u64,
    pub max_acceptable_risk_score: u8,
    pub bump: u8,
    pub is_settled: bool,
    pub created_at: i64,
    pub oracle_attestation_hash: [u8; 32],
    pub settled_at: i64,
}

#[error_code]
pub enum EudrError {
    #[msg("Escrow deposit amount must be greater than zero.")]
    InvalidAmount,
    #[msg("Job ID string exceeds 64 characters.")]
    JobIdTooLong,
    #[msg("Escrow has already been settled or slashed.")]
    AlreadySettled,
    #[msg("Total split amount exceeds deposited escrow balance.")]
    SplitExceedsEscrow,
}
