import os
from PIL import Image, ImageDraw, ImageFont

ARTIFACT_DIR = r"C:\Users\nohos\.gemini\antigravity-ide\brain\3fdef21b-0ffa-4486-93d9-1b6c46dc24f3"
os.makedirs(ARTIFACT_DIR, exist_ok=True)
OUT_GIF_WORKSPACE = "eudr_usage_tutorial.gif"
OUT_WEBP_WORKSPACE = "eudr_usage_tutorial.webp"
OUT_GIF_ARTIFACT = os.path.join(ARTIFACT_DIR, "eudr_usage_tutorial.gif")
OUT_WEBP_ARTIFACT = os.path.join(ARTIFACT_DIR, "eudr_usage_tutorial.webp")

WIDTH, HEIGHT = 1280, 720

# Universal World-Class Typography
FONT_BRAND = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 22)
FONT_HERO_TITLE = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 32)
FONT_HERO_SUB = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 18)
FONT_STEP_NUM = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 15)
FONT_STEP_LABEL = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 15)
FONT_CARD_HEAD = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 22)
FONT_CARD_BODY = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 15)
FONT_CODE = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 14)
FONT_BADGE = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 13)
FONT_CTA = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 18)

# Apple/Stripe-Level Dark Tech Palette
BG_MAIN = (8, 12, 20)            # Deep Space Black
BG_CARD = (18, 24, 38)           # Slate Glass
BG_CARD_INNER = (12, 17, 28)     # Pure Contrast
BORDER_MUTED = (38, 48, 68)      # Sleek Border
BORDER_ACTIVE = (59, 130, 246)   # Electric Blue
EMERALD_GREEN = (16, 185, 129)   # #10b981
EMERALD_BG = (6, 78, 59)
ELECTRIC_BLUE = (59, 130, 246)
ACCENT_RED = (239, 68, 68)
RED_BG = (69, 10, 10)
TEXT_WHITE = (255, 255, 255)
TEXT_MUTED = (148, 163, 184)
TEXT_DARK = (8, 12, 20)

STEPS = [
    ("1", "📁 1. UPLOAD"),
    ("2", "🛰️ 2. SCAN"),
    ("3", "🛡️ 3. VERIFY"),
    ("4", "⚡ 4. EXPORT")
]

def draw_top_nav(draw):
    draw.rectangle([0, 0, WIDTH, 48], fill=(12, 16, 26))
    draw.line([0, 48, WIDTH, 48], fill=BORDER_MUTED, width=1)
    draw.text((30, 10), "🌲 EUDR Agent", fill=TEXT_WHITE, font=FONT_BRAND)
    draw.text((215, 14), "eudragent.com", fill=ELECTRIC_BLUE, font=FONT_STEP_LABEL)
    
    draw.rounded_rectangle([WIDTH - 250, 9, WIDTH - 140, 39], radius=6, fill=EMERALD_BG, outline=EMERALD_GREEN)
    draw.text((WIDTH - 238, 14), "● TRACES-NT", fill=EMERALD_GREEN, font=FONT_BADGE)
    
    draw.rounded_rectangle([WIDTH - 130, 9, WIDTH - 30, 39], radius=6, fill=BG_CARD, outline=BORDER_MUTED)
    draw.text((WIDTH - 105, 14), "Global", fill=TEXT_WHITE, font=FONT_BADGE)

def draw_workflow_tracker(draw, active_idx):
    bar_y = 56
    bar_h = 44
    draw.rounded_rectangle([30, bar_y, WIDTH - 30, bar_y + bar_h], radius=8, fill=BG_CARD, outline=BORDER_MUTED)
    step_w = (WIDTH - 60) // 4
    for i, (num, label) in enumerate(STEPS):
        sx = 30 + i * step_w
        is_active = (i == active_idx)
        is_done = (active_idx is not None and i < active_idx)
        
        if is_active:
            draw.rounded_rectangle([sx + 8, bar_y + 4, sx + step_w - 8, bar_y + bar_h - 4], radius=6, fill=(30, 58, 138), outline=ELECTRIC_BLUE, width=2)
            num_col, text_col = TEXT_WHITE, TEXT_WHITE
        elif is_done:
            draw.rounded_rectangle([sx + 8, bar_y + 4, sx + step_w - 8, bar_y + bar_h - 4], radius=6, fill=EMERALD_BG)
            num_col, text_col = (167, 243, 208), (167, 243, 208)
        else:
            num_col, text_col = TEXT_MUTED, TEXT_MUTED
            
        draw.text((sx + 28, bar_y + 12), label, fill=text_col, font=FONT_STEP_LABEL)
        if i < 3:
            draw.text((sx + step_w - 12, bar_y + 11), "➔", fill=BORDER_MUTED, font=FONT_STEP_LABEL)

def draw_step_banner(draw, badge_text, main_text, sub_text):
    draw.rounded_rectangle([30, 108, WIDTH - 30, 162], radius=8, fill=(16, 26, 44), outline=ELECTRIC_BLUE, width=2)
    draw.rounded_rectangle([45, 116, 145, 154], radius=6, fill=ELECTRIC_BLUE)
    draw.text((60, 122), badge_text, fill=TEXT_WHITE, font=FONT_HERO_SUB)
    draw.text((165, 116), main_text, fill=TEXT_WHITE, font=FONT_HERO_SUB)
    draw.text((165, 138), sub_text, fill=(147, 197, 253), font=FONT_STEP_LABEL)

def draw_cursor(draw, x, y, clicking=False):
    points = [
        (x, y), (x, y + 20), (x + 6, y + 15), (x + 13, y + 22),
        (x + 17, y + 18), (x + 10, y + 12), (x + 16, y + 12)
    ]
    draw.polygon(points, fill=(255, 255, 255), outline=(0, 0, 0))
    if clicking:
        draw.ellipse([x - 14, y - 14, x + 14, y + 14], outline=(96, 165, 250), width=3)

# ---------------- SCENES ----------------

def create_scene_1():
    # STEP 1: 1-Click Upload
    frames = []
    for p in range(3):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_MAIN)
        draw = ImageDraw.Draw(img)
        draw_top_nav(draw)
        draw_workflow_tracker(draw, 0)
        draw_step_banner(draw, "STEP 1", "Select Preset or Drop GeoJSON", "1-Click load polygon coordinates & legal permits.")
        
        # Presets Bar
        draw.rounded_rectangle([30, 172, WIDTH - 30, 216], radius=6, fill=BG_CARD, outline=BORDER_MUTED)
        draw.text((45, 185), "⚡ Quick Scenario:", fill=TEXT_MUTED, font=FONT_STEP_LABEL)
        
        btn_hl = ELECTRIC_BLUE if p >= 1 else (26, 36, 54)
        draw.rounded_rectangle([190, 178, 430, 210], radius=6, fill=btn_hl, outline=ELECTRIC_BLUE)
        draw.text((205, 185), "🟢 Compliant Coffee (VN)", fill=TEXT_WHITE, font=FONT_STEP_LABEL)
        
        draw.rounded_rectangle([445, 178, 680, 210], radius=6, fill=(26, 36, 54), outline=BORDER_MUTED)
        draw.text((460, 185), "🔴 Deforestation (ID)", fill=TEXT_WHITE, font=FONT_STEP_LABEL)

        # Left Column
        draw.rounded_rectangle([30, 226, 520, HEIGHT - 20], radius=8, fill=BG_CARD, outline=BORDER_MUTED)
        draw.text((50, 246), "📋 Farm & Permit Input", fill=TEXT_WHITE, font=FONT_CARD_HEAD)
        draw.text((50, 285), "• Commodity: Coffee (0901.11)", fill=TEXT_WHITE, font=FONT_STEP_LABEL)
        draw.text((50, 315), "• Origin: Vietnam (5.4 ha Polygon)", fill=TEXT_WHITE, font=FONT_STEP_LABEL)
        draw.text((50, 345), "• Legal Permit: VN-FPD-2024 (Valid)", fill=TEXT_WHITE, font=FONT_STEP_LABEL)
        
        draw.rounded_rectangle([50, 385, 500, 490], radius=6, fill=BG_CARD_INNER, outline=BORDER_MUTED)
        draw.text((65, 405), 'Polygon: [[[108.441, 11.940],\n          [108.448, 11.942],\n          [108.449, 11.935]]]', fill=(96, 165, 250), font=FONT_CODE)

        draw.rounded_rectangle([50, 525, 500, 595], radius=8, fill=EMERALD_GREEN)
        draw.text((105, 548), "🚀 Run 5-Pillar Verification", fill=TEXT_DARK, font=FONT_CTA)

        # Right Column
        draw.rounded_rectangle([535, 226, WIDTH - 30, HEIGHT - 20], radius=8, fill=BG_CARD, outline=BORDER_MUTED)
        draw.text((555, 246), "🗺️ Satellite Spatial Radar", fill=TEXT_WHITE, font=FONT_CARD_HEAD)
        draw.rounded_rectangle([555, 280, WIDTH - 50, HEIGHT - 38], radius=6, fill=BG_CARD_INNER, outline=BORDER_MUTED)
        
        if p >= 1:
            poly = [(660, 380), (840, 360), (910, 520), (740, 560), (660, 380)]
            draw.polygon(poly, fill=(6, 78, 59), outline=EMERALD_GREEN)
            draw.text((720, 440), "📍 Lam Dong Plot (5.4 ha)\nReady for Audit", fill=TEXT_WHITE, font=FONT_STEP_LABEL)
        else:
            draw.text((730, 440), "Loading Plot...", fill=TEXT_MUTED, font=FONT_STEP_LABEL)

        cx = 230 + p * 80
        cy = 210 - p * 15
        draw_cursor(draw, cx, cy, clicking=(p >= 1))
        frames.append(img)
    return frames

def create_scene_2():
    # STEP 2: 2s Scan
    frames = []
    for p in range(4):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_MAIN)
        draw = ImageDraw.Draw(img)
        draw_top_nav(draw)
        draw_workflow_tracker(draw, 1)
        draw_step_banner(draw, "STEP 2", "Autonomous Satellite Radar Scan", "Checking Sentinel-2 & Hansen 2020 baseline in 2s.")
        
        draw.rounded_rectangle([30, 172, WIDTH - 30, 216], radius=6, fill=BG_CARD, outline=BORDER_MUTED)
        draw.rounded_rectangle([190, 178, 430, 210], radius=6, fill=ELECTRIC_BLUE, outline=ELECTRIC_BLUE)
        draw.text((205, 185), "🟢 Compliant Coffee (VN)", fill=TEXT_WHITE, font=FONT_STEP_LABEL)

        draw.rounded_rectangle([30, 226, 520, HEIGHT - 20], radius=8, fill=BG_CARD, outline=BORDER_MUTED)
        draw.text((50, 246), "📋 5-Pillar Engine Scanning...", fill=TEXT_WHITE, font=FONT_CARD_HEAD)
        draw.rounded_rectangle([50, 285, 500, 420], radius=6, fill=BG_CARD_INNER, outline=BORDER_MUTED)
        draw.text((65, 305), "✓ Validating Forest Permit VN-FPD\n✓ Calculating Geodesic Polygon Area\n✓ Scanning Sentinel-2 NDVI Radar\n✓ Verifying 2020 Forest Baseline...", fill=(52, 211, 153), font=FONT_CODE)

        btn_bg = (13, 148, 136) if (p % 2 == 0) else EMERALD_GREEN
        draw.rounded_rectangle([50, 445, 500, 515], radius=8, fill=btn_bg)
        draw.text((125, 468), "🛰️ Scanning Satellites...", fill=TEXT_DARK, font=FONT_CTA)

        # Right Column: Radar Scan
        draw.rounded_rectangle([535, 226, WIDTH - 30, HEIGHT - 20], radius=8, fill=BG_CARD, outline=BORDER_MUTED)
        draw.text((555, 246), "🗺️ Live Multi-Satellite Radar", fill=TEXT_WHITE, font=FONT_CARD_HEAD)
        draw.rounded_rectangle([555, 280, WIDTH - 50, HEIGHT - 38], radius=6, fill=BG_CARD_INNER, outline=EMERALD_GREEN)
        
        poly = [(660, 360), (840, 340), (910, 500), (740, 540), (660, 360)]
        draw.polygon(poly, fill=(6, 78, 59), outline=EMERALD_GREEN)
        
        radius = 35 + p * 45
        draw.ellipse([780 - radius, 440 - radius, 780 + radius, 440 + radius], outline=(52, 211, 153), width=2)
        draw.text((720, 570), f"Radar Progress: {p * 33}%", fill=TEXT_WHITE, font=FONT_STEP_LABEL)

        cx = 270
        cy = 475
        draw_cursor(draw, cx, cy, clicking=(p == 0))
        frames.append(img)
    return frames

def create_scene_3():
    # STEP 3: 100% Pass
    frames = []
    for p in range(3):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_MAIN)
        draw = ImageDraw.Draw(img)
        draw_top_nav(draw)
        draw_workflow_tracker(draw, 2)
        draw_step_banner(draw, "STEP 3", "100% Verified Compliance (PASS)", "Zero deforestation & legal harvest verified.")
        
        draw.rounded_rectangle([30, 172, 520, HEIGHT - 20], radius=8, fill=BG_CARD, outline=EMERALD_GREEN, width=2)
        draw.text((50, 192), "✅ Verdict: COMPLIANT (PASS)", fill=EMERALD_GREEN, font=FONT_CARD_HEAD)
        draw.text((50, 222), "Risk Score: 0.00 (LOW RISK)", fill=TEXT_WHITE, font=FONT_STEP_LABEL)

        badges = [
            ("Pillar 1: Deforestation-Free", "0.0% Forest Loss since 2020"),
            ("Pillar 2: Legal Harvest", "National Permit Validated"),
            ("Pillar 3: Polygon Topology", "5.4ha Closed Polygon Valid"),
            ("Pillar 4: TRACES-NT Ready", "100% Schema Conformity"),
            ("Pillar 5: Chain of Custody", "Traceability Verified")
        ]

        by = 255
        for name, desc in badges:
            draw.rounded_rectangle([50, by, 500, by + 48], radius=6, fill=EMERALD_BG, outline=EMERALD_GREEN)
            draw.text((65, by + 8), f"✔ {name}", fill=EMERALD_GREEN, font=FONT_STEP_LABEL)
            draw.text((65, by + 26), desc, fill=TEXT_WHITE, font=FONT_CODE)
            by += 56

        draw.rounded_rectangle([50, 550, 500, 615], radius=6, fill=ELECTRIC_BLUE)
        draw.text((120, 572), "📄 Download Official PDF Report", fill=TEXT_WHITE, font=FONT_CTA)

        draw.rounded_rectangle([535, 172, WIDTH - 30, HEIGHT - 20], radius=8, fill=BG_CARD, outline=BORDER_MUTED)
        draw.text((555, 192), "🗺️ Verified Farm Map", fill=TEXT_WHITE, font=FONT_CARD_HEAD)
        draw.rounded_rectangle([555, 228, WIDTH - 50, HEIGHT - 38], radius=6, fill=BG_CARD_INNER, outline=EMERALD_GREEN)
        poly = [(660, 310), (840, 290), (920, 460), (740, 510), (660, 310)]
        draw.polygon(poly, fill=(6, 78, 59), outline=EMERALD_GREEN)
        draw.text((710, 380), "🌲 Lam Dong Plot (5.4 ha)\nStatus: VERIFIED PASS", fill=TEXT_WHITE, font=FONT_STEP_LABEL)

        draw.rounded_rectangle([570, HEIGHT - 85, WIDTH - 65, HEIGHT - 50], radius=6, fill=(26, 36, 54))
        draw.text((590, HEIGHT - 72), "Hansen Loss: 0.00 ha | Canopy: 89.2% | Sentinel NDVI: 0.76 (PASS)", fill=(52, 211, 153), font=FONT_CODE)

        frames.append(img)
    return frames

def create_scene_4():
    # STEP 4: 1-Click TRACES-NT XML
    frames = []
    for p in range(3):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_MAIN)
        draw = ImageDraw.Draw(img)
        draw_top_nav(draw)
        draw_workflow_tracker(draw, 3)
        draw_step_banner(draw, "STEP 4", "Export Official TRACES-NT XML (DDS)", "1-click download of EU customs-ready filing document.")
        
        draw.rounded_rectangle([30, 172, WIDTH - 30, HEIGHT - 20], radius=8, fill=BG_CARD, outline=ELECTRIC_BLUE)
        draw.text((50, 192), "📄 TRACES-NT XML Payload", fill=TEXT_WHITE, font=FONT_CARD_HEAD)
        
        draw.rounded_rectangle([WIDTH - 360, 182, WIDTH - 230, 222], radius=6, fill=ELECTRIC_BLUE)
        draw.text((WIDTH - 340, 194), "📋 Copy XML", fill=TEXT_WHITE, font=FONT_STEP_LABEL)
        
        draw.rounded_rectangle([WIDTH - 220, 182, WIDTH - 50, 222], radius=6, fill=EMERALD_GREEN)
        draw.text((WIDTH - 200, 194), "💾 Download .xml", fill=TEXT_DARK, font=FONT_STEP_LABEL)

        draw.rounded_rectangle([50, 236, WIDTH - 50, HEIGHT - 38], radius=6, fill=(8, 12, 22), outline=BORDER_MUTED)
        xml_text = """<?xml version="1.0" encoding="UTF-8"?>
<eudr:DueDiligenceStatement xmlns:eudr="urn:eu:eudr:traces:v1">
  <eudr:ReferenceNumber>DDS-EUDR-2026-VN-994821</eudr:ReferenceNumber>
  <eudr:HarmonizedSystemCode>0901.11.00 (Coffee)</eudr:HarmonizedSystemCode>
  <eudr:Coordinates>108.441,11.940 108.448,11.942 108.449,11.935</eudr:Coordinates>
  <eudr:DeforestationFreeStatus>VERIFIED_TRUE (PASS)</eudr:DeforestationFreeStatus>
</eudr:DueDiligenceStatement>"""
        draw.text((65, 255), xml_text, fill=(96, 165, 250), font=FONT_CODE)

        if p >= 1:
            draw_cursor(draw, WIDTH - 120, 202, clicking=True)
        frames.append(img)
    return frames

def create_scene_5_master_climax():
    # WORLD-CLASS MINIMALIST CLIMAX: 1-SECOND AHA MOMENT
    frames = []
    for p in range(4):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_MAIN)
        draw = ImageDraw.Draw(img)
        draw_top_nav(draw)
        
        # Big Hero Header
        draw.rounded_rectangle([30, 58, WIDTH - 30, 130], radius=8, fill=(16, 26, 48), outline=ELECTRIC_BLUE, width=2)
        draw.text((50, 70), "💡 WHY EUDR AGENT?  (Instant Problem Solver)", fill=TEXT_WHITE, font=FONT_HERO_TITLE)
        draw.text((50, 104), "Zero fines. Zero customs delays. 100% automated.", fill=(147, 197, 253), font=FONT_HERO_SUB)

        # 3 High-Impact Cards (Minimal words, big icons, unmistakable contrast)
        cards = [
            (
                "❌  4% REVENUE FINES",
                "Blocked Cargo at EU Customs",
                "➔",
                "✅  0% FINE GUARANTEE",
                "Verified 5-Pillar Audit Trail"
            ),
            (
                "❌  WEEKS OF GIS WORK",
                "Slow, Costly Manual Satellite Checks",
                "➔",
                "✅  2-SECOND RADAR SCAN",
                "1-Click Sentinel & Hansen Analysis"
            ),
            (
                "❌  CUSTOMS XML ERRORS",
                "Rejected Due Diligence Filings",
                "➔",
                "✅  OFFICIAL TRACES-NT XML",
                "Customs-Validated 1-Click Export"
            )
        ]

        cy = 145
        for pain_head, pain_sub, arrow, sol_head, sol_sub in cards:
            draw.rounded_rectangle([30, cy, WIDTH - 30, cy + 125], radius=8, fill=BG_CARD, outline=BORDER_MUTED)
            
            # Left: Pain (Red)
            draw.rounded_rectangle([42, cy + 8, 590, cy + 117], radius=6, fill=RED_BG, outline=(185, 28, 28))
            draw.text((60, cy + 24), pain_head, fill=(254, 202, 202), font=FONT_CARD_HEAD)
            draw.text((60, cy + 64), pain_sub, fill=TEXT_MUTED, font=FONT_HERO_SUB)

            # Center Arrow
            draw.text((608, cy + 42), arrow, fill=ELECTRIC_BLUE, font=FONT_HERO_TITLE)

            # Right: Solution (Green)
            draw.rounded_rectangle([645, cy + 8, WIDTH - 42, cy + 117], radius=6, fill=EMERALD_BG, outline=EMERALD_GREEN)
            draw.text((665, cy + 24), sol_head, fill=(167, 243, 208), font=FONT_CARD_HEAD)
            draw.text((665, cy + 64), sol_sub, fill=TEXT_WHITE, font=FONT_HERO_SUB)

            cy += 135

        # Bottom Clean Punchy CTA
        draw.rounded_rectangle([30, HEIGHT - 70, WIDTH - 30, HEIGHT - 15], radius=8, fill=ELECTRIC_BLUE)
        draw.text((220, HEIGHT - 52), "🚀 Start Free Audit at eudragent.com  |  Zero Fines. Instant Clearance.", fill=TEXT_WHITE, font=FONT_HERO_SUB)

        frames.append(img)
    return frames

def main():
    print("Generating World-Class Minimalist EUDR Video Tutorial...")
    all_frames = []
    
    all_frames.extend(create_scene_1())
    all_frames.extend(create_scene_2())
    all_frames.extend(create_scene_3())
    all_frames.extend(create_scene_4())
    all_frames.extend(create_scene_5_master_climax())
    
    durations = [1200] * len(all_frames)
    for i in range(len(all_frames) - 4, len(all_frames)):
        durations[i] = 4500
    
    print(f"Total Frames: {len(all_frames)}")
    
    all_frames[0].save(
        OUT_GIF_WORKSPACE,
        save_all=True,
        append_images=all_frames[1:],
        duration=durations,
        loop=0,
        optimize=True
    )
    all_frames[0].save(
        OUT_GIF_ARTIFACT,
        save_all=True,
        append_images=all_frames[1:],
        duration=durations,
        loop=0,
        optimize=True
    )
    print(f"Saved GIF: {OUT_GIF_WORKSPACE}")

    all_frames[0].save(
        OUT_WEBP_WORKSPACE,
        format="WEBP",
        save_all=True,
        append_images=all_frames[1:],
        duration=durations,
        loop=0,
        lossless=False,
        quality=90
    )
    all_frames[0].save(
        OUT_WEBP_ARTIFACT,
        format="WEBP",
        save_all=True,
        append_images=all_frames[1:],
        duration=durations,
        loop=0,
        lossless=False,
        quality=90
    )
    print(f"Saved WebP: {OUT_WEBP_WORKSPACE}")

if __name__ == "__main__":
    main()
