# File: app/utils/unit_converter.py

import logging
from typing import Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class UnitCategory(Enum):
    """Categories of units for conversion"""
    LENGTH = "length"
    AREA = "area"
    VOLUME = "volume"
    WEIGHT = "weight"
    COUNT = "count"
    UNKNOWN = "unknown"


class UnitConverter:
    """
    Handles unit conversions for material cost calculations.
    Supports common units used in crafting and manufacturing.
    """

    # Define conversion factors to base units
    # Base units: meter (length), square_meter (area), liter (volume), gram (weight), piece (count)

    LENGTH_CONVERSIONS = {
        # All to meters
        "mm": 0.001,
        "millimeter": 0.001,
        "millimeters": 0.001,
        "cm": 0.01,
        "centimeter": 0.01,
        "centimeters": 0.01,
        "m": 1.0,
        "meter": 1.0,
        "meters": 1.0,
        "km": 1000.0,
        "kilometer": 1000.0,
        "kilometers": 1000.0,
        "in": 0.0254,
        "inch": 0.0254,
        "inches": 0.0254,
        "ft": 0.3048,
        "foot": 0.3048,
        "feet": 0.3048,
        "yd": 0.9144,
        "yard": 0.9144,
        "yards": 0.9144,
    }

    AREA_CONVERSIONS = {
        # All to square meters
        "mm2": 0.000001,
        "cm2": 0.0001,
        "m2": 1.0,
        "km2": 1000000.0,
        "in2": 0.00064516,
        "ft2": 0.092903,
        "yd2": 0.836127,
        "sq_mm": 0.000001,
        "sq_cm": 0.0001,
        "sq_m": 1.0,
        "sq_km": 1000000.0,
        "sq_in": 0.00064516,
        "sq_ft": 0.092903,
        "sq_yd": 0.836127,
        "square_millimeter": 0.000001,
        "square_centimeter": 0.0001,
        "square_meter": 1.0,
        "square_kilometer": 1000000.0,
        "square_inch": 0.00064516,
        "square_foot": 0.092903,
        "square_yard": 0.836127,
    }

    VOLUME_CONVERSIONS = {
        # All to liters
        "ml": 0.001,
        "milliliter": 0.001,
        "milliliters": 0.001,
        "l": 1.0,
        "liter": 1.0,
        "liters": 1.0,
        "cl": 0.01,
        "centiliter": 0.01,
        "centiliters": 0.01,
        "dl": 0.1,
        "deciliter": 0.1,
        "deciliters": 0.1,
        "m3": 1000.0,
        "cubic_meter": 1000.0,
        "cm3": 0.001,
        "cubic_centimeter": 0.001,
        "mm3": 0.000001,
        "cubic_millimeter": 0.000001,
        "in3": 0.0163871,
        "cubic_inch": 0.0163871,
        "ft3": 28.3168,
        "cubic_foot": 28.3168,
        "fl_oz": 0.0295735,
        "fluid_ounce": 0.0295735,
        "cup": 0.236588,
        "cups": 0.236588,
        "pint": 0.473176,
        "pints": 0.473176,
        "quart": 0.946353,
        "quarts": 0.946353,
        "gallon": 3.78541,
        "gallons": 3.78541,
    }

    WEIGHT_CONVERSIONS = {
        # All to grams
        "mg": 0.001,
        "milligram": 0.001,
        "milligrams": 0.001,
        "g": 1.0,
        "gram": 1.0,
        "grams": 1.0,
        "kg": 1000.0,
        "kilogram": 1000.0,
        "kilograms": 1000.0,
        "oz": 28.3495,
        "ounce": 28.3495,
        "ounces": 28.3495,
        "lb": 453.592,
        "pound": 453.592,
        "pounds": 453.592,
        "lbs": 453.592,
        "ton": 1000000.0,
        "tons": 1000000.0,
        "tonne": 1000000.0,
        "tonnes": 1000000.0,
    }

    COUNT_CONVERSIONS = {
        # All to pieces
        "piece": 1.0,
        "pieces": 1.0,
        "pcs": 1.0,
        "pc": 1.0,
        "item": 1.0,
        "items": 1.0,
        "unit": 1.0,
        "units": 1.0,
        "each": 1.0,
        "ea": 1.0,
        "dozen": 12.0,
        "doz": 12.0,
        "pair": 2.0,
        "pairs": 2.0,
        "set": 1.0,
        "sets": 1.0,
    }

    def __init__(self):
        """Initialize the unit converter with all conversion tables."""
        self.conversions = {
            UnitCategory.LENGTH: self.LENGTH_CONVERSIONS,
            UnitCategory.AREA: self.AREA_CONVERSIONS,
            UnitCategory.VOLUME: self.VOLUME_CONVERSIONS,
            UnitCategory.WEIGHT: self.WEIGHT_CONVERSIONS,
            UnitCategory.COUNT: self.COUNT_CONVERSIONS,
        }

    def normalize_unit(self, unit: str) -> str:
        """Normalize unit string by removing spaces, converting to lowercase."""
        if not unit:
            return ""
        return unit.strip().lower().replace(" ", "_")

    def get_unit_category(self, unit: str) -> UnitCategory:
        """Determine which category a unit belongs to."""
        normalized = self.normalize_unit(unit)

        for category, conversion_dict in self.conversions.items():
            if normalized in conversion_dict:
                return category

        return UnitCategory.UNKNOWN

    def can_convert(self, from_unit: str, to_unit: str) -> bool:
        """Check if conversion is possible between two units."""
        from_category = self.get_unit_category(from_unit)
        to_category = self.get_unit_category(to_unit)

        return (from_category != UnitCategory.UNKNOWN and
                to_category != UnitCategory.UNKNOWN and
                from_category == to_category)

    def convert(self, value: float, from_unit: str, to_unit: str) -> Tuple[float, bool, str]:
        """
        Convert a value from one unit to another.

        Args:
            value: The numeric value to convert
            from_unit: Source unit
            to_unit: Target unit

        Returns:
            Tuple of (converted_value, success, error_message)
        """
        if value == 0:
            return 0.0, True, ""

        from_normalized = self.normalize_unit(from_unit)
        to_normalized = self.normalize_unit(to_unit)

        # Same unit, no conversion needed
        if from_normalized == to_normalized:
            return value, True, ""

        # Check if conversion is possible
        if not self.can_convert(from_unit, to_unit):
            from_category = self.get_unit_category(from_unit)
            to_category = self.get_unit_category(to_unit)

            if from_category == UnitCategory.UNKNOWN:
                error_msg = f"Unknown unit: '{from_unit}'"
            elif to_category == UnitCategory.UNKNOWN:
                error_msg = f"Unknown unit: '{to_unit}'"
            else:
                error_msg = f"Cannot convert between {from_category.value} and {to_category.value}"

            return value, False, error_msg

        # Get the category and conversion factors
        category = self.get_unit_category(from_unit)
        conversion_dict = self.conversions[category]

        try:
            # Convert to base unit, then to target unit
            from_factor = conversion_dict[from_normalized]
            to_factor = conversion_dict[to_normalized]

            base_value = value * from_factor
            converted_value = base_value / to_factor

            return converted_value, True, ""

        except KeyError as e:
            error_msg = f"Conversion factor not found for unit: {e}"
            logger.error(f"Unit conversion error: {error_msg}")
            return value, False, error_msg
        except ZeroDivisionError:
            error_msg = f"Invalid conversion factor for unit: '{to_unit}'"
            logger.error(f"Unit conversion error: {error_msg}")
            return value, False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error during conversion: {str(e)}"
            logger.error(f"Unit conversion error: {error_msg}", exc_info=True)
            return value, False, error_msg

    def get_conversion_factor(self, from_unit: str, to_unit: str) -> Tuple[float, bool, str]:
        """
        Get the conversion factor from one unit to another.

        Args:
            from_unit: Source unit
            to_unit: Target unit

        Returns:
            Tuple of (conversion_factor, success, error_message)
            If successful, multiply by this factor to convert from_unit to to_unit
        """
        converted_value, success, error_msg = self.convert(1.0, from_unit, to_unit)
        return converted_value, success, error_msg

    def get_supported_units(self) -> Dict[str, list]:
        """Get all supported units organized by category."""
        supported = {}
        for category, conversion_dict in self.conversions.items():
            supported[category.value] = list(conversion_dict.keys())
        return supported

    def suggest_units(self, unit: str) -> list:
        """Suggest similar units when an exact match isn't found."""
        normalized = self.normalize_unit(unit)
        suggestions = []

        for category, conversion_dict in self.conversions.items():
            for supported_unit in conversion_dict.keys():
                if (normalized in supported_unit or
                        supported_unit in normalized or
                        abs(len(normalized) - len(supported_unit)) <= 2):
                    suggestions.append(supported_unit)

        return suggestions[:5]  # Limit to top 5 suggestions


# Global instance for easy import
unit_converter = UnitConverter()


if __name__ == "__main__":
    # Example usage and tests
    converter = UnitConverter()

    # Test conversions
    test_cases = [
        (1.0, "meters", "feet"),
        (100.0, "grams", "pounds"),
        (1.0, "liters", "gallons"),
        (12.0, "inches", "centimeters"),
        (1.0, "dozen", "pieces"),
        (2.5, "square_feet", "square_meters"),
    ]

    print("Unit Conversion Tests:")
    print("-" * 50)

    for value, from_unit, to_unit in test_cases:
        converted, success, error = converter.convert(value, from_unit, to_unit)
        if success:
            print(f"{value} {from_unit} = {converted:.4f} {to_unit}")
        else:
            print(f"Error converting {value} {from_unit} to {to_unit}: {error}")

    print("\n" + "-" * 50)
    print("Supported unit categories:")
    for category, units in converter.get_supported_units().items():
        print(f"{category.title()}: {len(units)} units")