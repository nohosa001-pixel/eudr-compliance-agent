import math
from typing import Dict, Any, Tuple, Optional, List
from shapely.geometry import shape, Point, Polygon

class HansenGFCProvider:
    """
    Hansen Global Forest Change (UMD/Google/USGS) v1.10 Data Engine.
    - Resolves 10x10 degree granules (e.g. '00N_100E', '10S_050W').
    - Evaluates Hansen LossYear band values:
        * 0: No loss
        * 1-20: Loss in 2001-2020 (Pre-cutoff: EUDR Compliant)
        * 21-23+: Loss in 2021-2023+ (Post-2020: DEFORESTATION DETECTED)
    - Tree Canopy Cover 2000 baseline (treecover2000 threshold >= 10% forest definition).
    """

    GFC_BASE_URL = "https://storage.googleapis.com/earthenginepartners-hansen/GFC-2023-v1.11"
    CUTOFF_LOSS_YEAR_INDEX = 20  # 2020 corresponds to value 20

    @classmethod
    def get_granule_tile_id(cls, lon: float, lat: float) -> str:
        """
        Calculates the Hansen GFC 10x10 degree tile identifier for a given WGS84 coordinate.
        Format: [LatUpper][N/S]_[LonLeft][E/W] (e.g. lat 5.2, lon 101.3 -> '10N_100E').
        """
        # Upper latitude rounded up to nearest 10
        lat_ceil = math.ceil(lat / 10.0) * 10
        if lat_ceil > 80:
            lat_ceil = 80
        if lat_ceil < -80:
            lat_ceil = -80
        
        lat_dir = "N" if lat_ceil >= 0 else "S"
        lat_str = f"{abs(lat_ceil):02d}{lat_dir}"

        # Left longitude rounded down to nearest 10
        lon_floor = math.floor(lon / 10.0) * 10
        if lon_floor > 180:
            lon_floor = 180
        if lon_floor < -180:
            lon_floor = -180
        
        lon_dir = "E" if lon_floor >= 0 else "W"
        lon_str = f"{abs(lon_floor):03d}{lon_dir}"

        return f"{lat_str}_{lon_str}"

    @classmethod
    def get_tile_download_urls(cls, tile_id: str) -> Dict[str, str]:
        """Returns direct Cloud Storage GeoTIFF URLs for Hansen GFC bands."""
        return {
            "treecover2000": f"{cls.GFC_BASE_URL}/Hansen_GFC-2023-v1.11_treecover2000_{tile_id}.tif",
            "lossyear": f"{cls.GFC_BASE_URL}/Hansen_GFC-2023-v1.11_lossyear_{tile_id}.tif",
            "gain": f"{cls.GFC_BASE_URL}/Hansen_GFC-2023-v1.11_gain_{tile_id}.tif",
            "datamask": f"{cls.GFC_BASE_URL}/Hansen_GFC-2023-v1.11_datamask_{tile_id}.tif",
        }

    @classmethod
    def parse_hansen_loss(cls, lon: float, lat: float, loss_year_val: int, treecover_val: int) -> Dict[str, Any]:
        """
        Parses Hansen raster cell values into EUDR compliance criteria.
        """
        tile_id = cls.get_granule_tile_id(lon, lat)
        is_forest_baseline = treecover_val >= 10  # FAO / EUDR 10% canopy cover threshold

        if loss_year_val == 0:
            loss_year_actual = None
            is_post_2020_loss = False
        else:
            loss_year_actual = 2000 + loss_year_val
            is_post_2020_loss = loss_year_val > cls.CUTOFF_LOSS_YEAR_INDEX

        return {
            "tile_id": tile_id,
            "treecover_baseline_pct": treecover_val,
            "is_forest_baseline": is_forest_baseline,
            "loss_year_raster_value": loss_year_val,
            "loss_year_actual": loss_year_actual,
            "post_2020_deforestation": is_post_2020_loss,
            "tile_urls": cls.get_tile_download_urls(tile_id)
        }
