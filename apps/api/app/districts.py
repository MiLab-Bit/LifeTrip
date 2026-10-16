from pydantic import BaseModel


class District(BaseModel):
    id: str
    name: str
    city: str
    south: float
    west: float
    north: float
    east: float


DISTRICTS: list[District] = [
    # ── 上海 ──
    District(
        id="anfu-wukang",
        name="安福—武康",
        city="上海",
        south=31.204,
        west=121.434,
        north=31.218,
        east=121.448,
    ),
    District(
        id="yuyuan-js",
        name="愚园—江苏路",
        city="上海",
        south=31.216,
        west=121.418,
        north=31.228,
        east=121.432,
    ),
    District(
        id="jufu-fumin",
        name="巨富—富民",
        city="上海",
        south=31.214,
        west=121.448,
        north=31.222,
        east=121.456,
    ),
    District(
        id="west-bund",
        name="西岸—滨江",
        city="上海",
        south=31.178,
        west=121.448,
        north=31.198,
        east=121.472,
    ),
    # ── 北京 ──
    District(
        id="gulou-nanluo",
        name="鼓楼—南锣",
        city="北京",
        south=39.930,
        west=116.395,
        north=39.950,
        east=116.420,
    ),
    District(
        id="wudaoying",
        name="五道营胡同",
        city="北京",
        south=39.945,
        west=116.405,
        north=39.960,
        east=116.420,
    ),
    District(
        id="798-art",
        name="798 艺术区",
        city="北京",
        south=39.980,
        west=116.490,
        north=39.990,
        east=116.500,
    ),
    # ── 杭州 ──
    District(
        id="zhongshan-mid",
        name="中山中路",
        city="杭州",
        south=30.245,
        west=120.160,
        north=30.265,
        east=120.180,
    ),
    # ── 成都 ──
    District(
        id="taikoo-li",
        name="太古里—镋钯街",
        city="成都",
        south=30.640,
        west=104.070,
        north=30.665,
        east=104.090,
    ),
    District(
        id="yulin-road",
        name="玉林路",
        city="成都",
        south=30.635,
        west=104.065,
        north=30.650,
        east=104.080,
    ),
]

CITIES: list[str] = sorted({d.city for d in DISTRICTS})
