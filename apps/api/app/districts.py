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
]
