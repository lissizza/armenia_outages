import pytest
from parsers.power_parser import split_address


@pytest.mark.parametrize(
    "address, expected_area, expected_district, expected_house_number",
    [
        ("г.ЕРЕВАН, 5", "г.ЕРЕВАН", None, "5"),
        (
            "г.ЕРЕВАН, БАШИНДЖАГЯН УЛ. 2 6",
            "г.ЕРЕВАН",
            "БАШИНДЖАГЯН УЛ. 2",
            "6",
        ),
        (
            "г.ЕРЕВАН, НОРКИ 2 ул. 1 проезд 80,25",
            "г.ЕРЕВАН",
            "НОРКИ 2 ул. 1 проезд",
            "80,25",
        ),
        ("г.ЕРЕВАН, 17А", "г.ЕРЕВАН", None, "17А"),
        ("г.ЕРЕВАН, 25 корп. 1", "г.ЕРЕВАН", "25 корп.", "1"),
        ("г.ЕРЕВАН, САДОВАЯ ул. 1 проезд 23", "г.ЕРЕВАН", "САДОВАЯ ул. 1 проезд", "23"),
        ("г.ЕРЕВАН, УЛИЦА АРШАКЯНЦА 15", "г.ЕРЕВАН", "УЛИЦА АРШАКЯНЦА", "15"),
        (
            "г.ЕРЕВАН, БАШИНДЖАГЯН УЛ. 6,8,10",
            "г.ЕРЕВАН",
            "БАШИНДЖАГЯН УЛ.",
            "6,8,10",
        ),
        ("г.ЕРЕВАН", "г.ЕРЕВАН", None, None),
        ("г.ЕРЕВАН, НАЗАРБЕКЯН КВАРТ.", "г.ЕРЕВАН", "НАЗАРБЕКЯН КВАРТ.", None),
        ("г.ЕРЕВАН, МАЗМАНЯН УЛ. Հ.2", "г.ЕРЕВАН", "МАЗМАНЯН УЛ.", "Հ.2"),
        ("г.ЕРЕВАН, ШИРАЗИ УЛ. 5-6", "г.ЕРЕВАН", "ШИРАЗИ УЛ.", "5-6"),
        ("г.ЕРЕВАН, АРШАКЯНЦА ул.", "г.ЕРЕВАН", "АРШАКЯНЦА ул.", None),
        ("г.ЕРЕВАН, АРШАКЯНЦА ул. 85/1", "г.ЕРЕВАН", "АРШАКЯНЦА ул.", "85/1"),
        ("г.ЕРЕВАН, ШОЛОХОВ УЛ. 7 Բ", "г.ЕРЕВАН", "ШОЛОХОВ УЛ.", "7 Բ"),
        ("г.ЕРЕВАН, 7 Բ", "г.ЕРЕВАН", None, "7 Բ"),
    ],
)
def test_split_address(
    address, expected_area, expected_district, expected_house_number
):
    # Test the split_address function
    area, district, house_number = split_address(address)
    assert area.upper() == expected_area.upper()
    assert district == expected_district
    assert house_number == expected_house_number
