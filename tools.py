"""
Agent Tools: Functions that the AI agent can call to get real-time information.
"""

import os
import re
import time
import requests
from datetime import datetime, timedelta
from fractions import Fraction
from dotenv import load_dotenv

load_dotenv(override=True)


def get_current_time() -> str:
    """
    Get the current date and time with timezone information from an internet time source.
    
    Returns:
        str: Current date and time in format "Month Day, Year, HH:MM:SS AM/PM (UTC±HH:MM)"
    """
    try:
        # Try time.is JSON API first (more reliable)
        response = requests.get("https://time.is/JSON", timeout=3)
        if response.status_code == 200 and 'text' not in response.text:
            # Parse JSON response
            data = response.json()
            # time.is returns Unix timestamp in milliseconds
            timestamp_ms = data.get('unixtime')
            if timestamp_ms:
                from datetime import timezone as tz
                utc_dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=tz.utc)
                local_dt = utc_dt.astimezone()
                
                # Get local timezone offset
                offset = local_dt.utcoffset()
                total_seconds = int(offset.total_seconds())
                hours, remainder = divmod(abs(total_seconds), 3600)
                minutes = remainder // 60
                tz_sign = '+' if total_seconds >= 0 else '-'
                tz_string = f"UTC{tz_sign}{hours:02d}:{minutes:02d}"
                
                # Format the output
                time_str = local_dt.strftime("%B %d, %Y, %I:%M:%S %p")
                return f"{time_str} ({tz_string})"
    except Exception:
        pass
    
    try:
        # Fallback to worldtimeapi.org
        response = requests.get("http://worldtimeapi.org/api/timezone/Etc/UTC", timeout=3)
        if response.status_code == 200:
            data = response.json()
            utc_timestamp = data['unixtime']
            
            from datetime import timezone as tz
            utc_dt = datetime.fromtimestamp(utc_timestamp, tz=tz.utc)
            local_dt = utc_dt.astimezone()
            
            offset = local_dt.utcoffset()
            total_seconds = int(offset.total_seconds())
            hours, remainder = divmod(abs(total_seconds), 3600)
            minutes = remainder // 60
            tz_sign = '+' if total_seconds >= 0 else '-'
            tz_string = f"UTC{tz_sign}{hours:02d}:{minutes:02d}"
            
            time_str = local_dt.strftime("%B %d, %Y, %I:%M:%S %p")
            return f"{time_str} ({tz_string})"
    except Exception:
        pass
    
    # Final fallback: Get system time (may be incorrect if system clock is wrong)
    now = datetime.now()
    
    is_dst = time.daylight and time.localtime().tm_isdst > 0
    utc_offset = -(time.altzone if is_dst else time.timezone)
    hours, remainder = divmod(abs(utc_offset), 3600)
    minutes = remainder // 60
    tz_sign = '+' if utc_offset >= 0 else '-'
    tz_string = f"UTC{tz_sign}{hours:02d}:{minutes:02d}"
    
    time_str = now.strftime("%B %d, %Y, %I:%M:%S %p")
    return f"{time_str} ({tz_string}) [⚠️ System Time - May Be Incorrect]"


def get_current_weather(location: str = "New York") -> str:
    """
    Get current weather information for a specified location.
    
    Args:
        location: City name or "City, Country" (e.g., "London", "Paris, FR", "New York")
    
    Returns:
        str: Weather information including temperature, conditions, and humidity
    """
    try:
        api_key = os.getenv('OPENWEATHER_API_KEY')
        if not api_key:
            return "Weather service unavailable. API key not configured."
        
        base_url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': location,
            'appid': api_key,
            'units': 'imperial'  # Fahrenheit
        }
        
        response = requests.get(base_url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            city = data['name']
            country = data['sys']['country']
            temp = round(data['main']['temp'])
            feels_like = round(data['main']['feels_like'])
            description = data['weather'][0]['description'].title()
            humidity = data['main']['humidity']
            
            return (
                f"Weather in {city}, {country}:\n"
                f"Temperature: {temp}°F (feels like {feels_like}°F)\n"
                f"Conditions: {description}\n"
                f"Humidity: {humidity}%"
            )
        
        elif response.status_code == 404:
            return f"Location '{location}' not found. Please check the city name."
        else:
            return "Weather service temporarily unavailable."
            
    except requests.exceptions.Timeout:
        return "Weather service timeout. Please try again."
    except requests.exceptions.ConnectionError:
        return "Cannot connect to weather service. Check internet connection."
    except Exception as e:
        return f"Weather error: {str(e)}"


def search_recipes(query: str, max_results: int = 3) -> str:
    """
    Search for recipes using TheMealDB API based on a search query.
    
    Args:
        query: Recipe search term (e.g., "chocolate cake", "gluten free", "chicken")
        max_results: Maximum number of recipes to return (default: 3)
    
    Returns:
        str: Formatted recipe results with names, ingredients, and instructions
    """
    try:
        # TheMealDB free API endpoint
        base_url = "https://www.themealdb.com/api/json/v1/1/search.php"
        params = {'s': query}
        
        response = requests.get(base_url, params=params, timeout=5)
        
        if response.status_code != 200:
            return "Recipe search service temporarily unavailable."
        
        data = response.json()
        meals = data.get('meals')
        
        if not meals:
            return f"No recipes found for '{query}'. Try a different search term like 'chocolate cake', 'cookies', or 'brownies'."
        
        # Limit results
        meals = meals[:max_results]
        
        results = []
        for meal in meals:
            name = meal['strMeal']
            category = meal['strCategory']
            area = meal['strArea']
            
            # Collect ingredients
            ingredients = []
            for i in range(1, 21):  # TheMealDB has up to 20 ingredients
                ingredient = meal.get(f'strIngredient{i}')
                measure = meal.get(f'strMeasure{i}')
                if ingredient and ingredient.strip():
                    ingredients.append(f"{measure.strip()} {ingredient.strip()}" if measure and measure.strip() else ingredient.strip())
            
            instructions = meal['strInstructions']
            
            # Format the recipe
            recipe_text = f"{name} ({category}, {area} cuisine)\n\n"
            recipe_text += "Ingredients:\n" + "\n".join(f"  {ing}" for ing in ingredients) + "\n\n"
            recipe_text += f"Instructions:\n{instructions}\n"
            
            results.append(recipe_text)
        
        if len(results) == 1:
            return results[0]
        else:
            return "\n\n---\n\n".join(results)
            
    except requests.exceptions.Timeout:
        return "Recipe search timeout. Please try again."
    except requests.exceptions.ConnectionError:
        return "Cannot connect to recipe service. Check internet connection."
    except Exception as e:
        return f"Recipe search error: {str(e)}"


def convert_units(value: float, from_unit: str, to_unit: str, ingredient: str = "generic") -> str:
    """
    Convert between baking measurement units (cups, grams, ounces, tablespoons, teaspoons, milliliters).
    Accounts for ingredient density differences.
    
    Args:
        value: Amount to convert
        from_unit: Source unit (e.g., "cups", "grams", "ounces", "tbsp", "tsp", "ml")
        to_unit: Target unit
        ingredient: Type of ingredient for density-specific conversions (e.g., "flour", "sugar", "butter")
    
    Returns:
        str: Converted value with unit
    """
    try:
        # Density data (grams per cup) for common baking ingredients
        densities = {
            "flour": 120,
            "all-purpose flour": 120,
            "bread flour": 127,
            "cake flour": 114,
            "sugar": 200,
            "granulated sugar": 200,
            "brown sugar": 220,
            "powdered sugar": 120,
            "butter": 227,
            "cocoa powder": 85,
            "honey": 340,
            "milk": 244,
            "water": 237,
            "oil": 218,
            "generic": 200  # Default
        }
        
        # Normalize units
        unit_aliases = {
            "cups": "cup", "c": "cup",
            "grams": "gram", "g": "gram",
            "ounces": "ounce", "oz": "ounce",
            "tablespoons": "tbsp", "tablespoon": "tbsp", "T": "tbsp",
            "teaspoons": "tsp", "teaspoon": "tsp", "t": "tsp",
            "milliliters": "ml", "milliliter": "ml", "mL": "ml",
            "pounds": "lb", "pound": "lb", "lbs": "lb"
        }
        
        from_unit = unit_aliases.get(from_unit.lower(), from_unit.lower())
        to_unit = unit_aliases.get(to_unit.lower(), to_unit.lower())
        ingredient = ingredient.lower()
        
        # Get ingredient density (grams per cup)
        density = densities.get(ingredient, densities["generic"])
        
        # Convert to grams first (base unit)
        if from_unit == "gram":
            grams = value
        elif from_unit == "cup":
            grams = value * density
        elif from_unit == "ounce":
            grams = value * 28.35
        elif from_unit == "tbsp":
            grams = value * (density / 16)  # 16 tbsp per cup
        elif from_unit == "tsp":
            grams = value * (density / 48)  # 48 tsp per cup
        elif from_unit == "ml":
            grams = value * (density / 237)  # 237 ml per cup
        elif from_unit == "lb":
            grams = value * 453.592
        else:
            return f"Unsupported unit: {from_unit}. Supported units: cups, grams, ounces, tbsp, tsp, ml, pounds"
        
        # Convert from grams to target unit
        if to_unit == "gram":
            result = grams
        elif to_unit == "cup":
            result = grams / density
        elif to_unit == "ounce":
            result = grams / 28.35
        elif to_unit == "tbsp":
            result = grams / (density / 16)
        elif to_unit == "tsp":
            result = grams / (density / 48)
        elif to_unit == "ml":
            result = grams / (density / 237)
        elif to_unit == "lb":
            result = grams / 453.592
        else:
            return f"Unsupported unit: {to_unit}. Supported units: cups, grams, ounces, tbsp, tsp, ml, pounds"
        
        # Format result
        if result >= 100:
            result_str = f"{result:.0f}"
        elif result >= 10:
            result_str = f"{result:.1f}"
        else:
            result_str = f"{result:.2f}"
        
        return f"{value} {from_unit} of {ingredient} = {result_str} {to_unit}"
        
    except Exception as e:
        return f"Conversion error: {str(e)}"


_UNICODE_FRACTIONS = {
    "½": "1/2", "¼": "1/4", "¾": "3/4", "⅓": "1/3", "⅔": "2/3",
    "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8",
}
_UF = "".join(_UNICODE_FRACTIONS)
# Order matters: longer/more specific forms must be tried first.
_QTY = (
    rf"(?:\d+[ \t]*[{_UF}]|[{_UF}]|\d+[ \t]+\d+/\d+|\d+/\d+|\d*\.\d+|\d+)"
)
_LEADING_QTY_RE = re.compile(
    rf"^(?P<prefix>[ \t]*(?:[-*•][ \t]+)?)(?P<q1>{_QTY})"
    rf"(?:(?P<sep>[ \t]*(?:-|–|to)[ \t]*)(?P<q2>{_QTY}))?(?![\d/.])"
)
# A quantity followed by these is a temperature or duration, not an amount.
_NOT_AN_AMOUNT_RE = re.compile(
    r"(?:°|º|[FC]\b)|[ \t]*(?:degrees?\b|deg\b|min(?:ute)?s?\b|hours?\b|hrs?\b|sec(?:ond)?s?\b)",
    re.IGNORECASE,
)
_VOLUME_UNIT_RE = re.compile(r"[ \t]*(?:cups?|c|tbsp|tsp|tablespoons?|teaspoons?)\b", re.IGNORECASE)
_ITEM_SPLIT_RE = re.compile(rf",[ \t]*(?=[\d{_UF}]|\.\d)")
_NICE_FRACTIONS = [(Fraction(n, d), f"{n}/{d}") for d, n in
                   [(8, 1), (4, 1), (3, 1), (8, 3), (2, 1), (8, 5), (3, 2), (4, 3), (8, 7)]]


def _parse_quantity(text: str) -> Fraction:
    """Parse '1', '1.5', '1/2', '1 1/2', '½', or '1½' into an exact Fraction."""
    for char, ascii_frac in _UNICODE_FRACTIONS.items():
        if char in text:
            whole = text.replace(char, "").strip()
            return Fraction(ascii_frac) + (Fraction(whole) if whole else 0)
    parts = text.split()
    return sum(Fraction(p) for p in parts)


def _format_quantity(value: Fraction, as_fraction: bool) -> str:
    """Format a scaled amount as a tidy fraction ('1 1/2') or decimal ('4.5')."""
    if as_fraction:
        whole = int(value)
        remainder = value - whole
        if remainder < Fraction(1, 50):
            return str(whole)
        if remainder > Fraction(49, 50):
            return str(whole + 1)
        for candidate, label in _NICE_FRACTIONS:
            if abs(remainder - candidate) < Fraction(1, 50):
                return f"{whole} {label}" if whole else label
    number = float(value)
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _scale_ingredient_line(line: str, factor: Fraction) -> str:
    """Scale the leading quantity of one ingredient line; leave everything else as written."""
    match = _LEADING_QTY_RE.match(line)
    if not match:
        return line

    rest = line[match.end():]
    if _NOT_AN_AMOUNT_RE.match(rest):
        return line

    q1, q2 = match.group("q1"), match.group("q2")
    as_fraction = (
        "/" in q1 or (q2 is not None and "/" in q2)
        or any(c in q1 + (q2 or "") for c in _UNICODE_FRACTIONS)
        or bool(_VOLUME_UNIT_RE.match(rest))
    )

    try:
        scaled = _format_quantity(_parse_quantity(q1) * factor, as_fraction)
        if q2 is not None:
            scaled += match.group("sep") + _format_quantity(_parse_quantity(q2) * factor, as_fraction)
    except (ZeroDivisionError, ValueError):
        return line  # e.g. "1/0" - not a real quantity, leave it untouched

    return match.group("prefix") + scaled + rest


def scale_recipe(original_servings: int, desired_servings: int, ingredients_text: str) -> str:
    """
    Scale a recipe's ingredients from original servings to desired servings.

    Only the leading quantity of each ingredient is scaled (whole numbers, decimals,
    fractions like 1/2, mixed fractions like 1 1/2, and ranges like 1-2). Units, names
    and descriptions are preserved, and numbers such as oven temperatures or times are
    never scaled.

    Args:
        original_servings: Original number of servings
        desired_servings: Desired number of servings
        ingredients_text: List of ingredients with amounts (one per line, or comma-separated)

    Returns:
        str: Scaled ingredients list with adjusted quantities
    """
    try:
        if original_servings <= 0 or desired_servings <= 0:
            return "Error: Servings must be positive numbers"

        factor = Fraction(desired_servings) / Fraction(original_servings)

        # One ingredient per line; commas only separate items when a new quantity follows,
        # so descriptions like "1 cup butter, softened" stay intact.
        ingredients = [
            item.strip()
            for line in ingredients_text.splitlines()
            for item in _ITEM_SPLIT_RE.split(line)
            if item.strip()
        ]

        if not ingredients:
            return "No ingredients provided to scale"

        scaled_ingredients = [_scale_ingredient_line(item, factor) for item in ingredients]

        result = f"Scaling from {original_servings} to {desired_servings} servings (×{float(factor):.2f}):\n\n"
        result += "\n".join(f"  {ing}" for ing in scaled_ingredients)

        return result

    except Exception as e:
        return f"Scaling error: {str(e)}"


def _fmt_grams(value: float) -> str:
    """Format a weight in grams without trailing zeros (350.0 -> '350', 12.50 -> '12.5')."""
    return f"{value:.1f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))


def calculate_bakers_percentage(flour: float, water: float = 0, salt: float = 0,
                                 yeast: float = 0, sugar: float = 0, fat: float = 0,
                                 other: float = 0, target_hydration: float = None,
                                 extra_ingredients: dict = None) -> str:
    """
    Calculate baker's percentages for bread/dough recipes.
    All ingredients are expressed as percentages of the flour weight.

    Args:
        flour: Weight of flour in grams (the base - always 100%)
        water: Weight of water in grams
        salt: Weight of salt in grams
        yeast: Weight of yeast in grams
        sugar: Weight of sugar in grams
        fat: Weight of fat/butter/oil in grams
        other: Weight of other ingredients in grams
        target_hydration: Desired hydration percentage. When water is not given, the
            water weight needed to reach this hydration is calculated.
        extra_ingredients: Any additional named ingredients in grams,
            e.g. {"eggs": 100, "milk": 60, "sourdough starter": 120}

    Returns:
        str: Baker's percentage breakdown with the hydration calculation and total weight
    """
    try:
        if flour <= 0:
            return "Error: Flour weight must be greater than 0"

        extras = {str(name).strip(): float(grams) for name, grams in (extra_ingredients or {}).items()}
        amounts = [water, salt, yeast, sugar, fat, other, *extras.values()]
        if any(a < 0 for a in amounts):
            return "Error: Ingredient weights cannot be negative"
        if target_hydration is not None and target_hydration < 0:
            return "Error: Target hydration cannot be negative"

        # Work out water from a target hydration when no water weight was given
        water_note = ""
        if target_hydration is not None and water == 0:
            water = flour * target_hydration / 100
            water_note = (
                f"  Water needed = flour × hydration ÷ 100\n"
                f"               = {_fmt_grams(flour)} × {target_hydration:g} ÷ 100 "
                f"= {_fmt_grams(round(water, 1))}g\n\n"
            )

        # Calculate percentages (flour is always 100%)
        water_pct = (water / flour) * 100
        salt_pct = (salt / flour) * 100
        yeast_pct = (yeast / flour) * 100
        sugar_pct = (sugar / flour) * 100
        fat_pct = (fat / flour) * 100
        other_pct = (other / flour) * 100

        # Total percentage and weight
        total_weight = flour + water + salt + yeast + sugar + fat + other + sum(extras.values())
        total_pct = total_weight / flour * 100

        # Format output
        result = water_note
        result += f"Baker's Percentage (based on {_fmt_grams(flour)}g flour):\n\n"
        result += f"  Flour:  100.0% ({_fmt_grams(flour)}g)\n"

        if water > 0:
            result += f"  Water:  {water_pct:.1f}% ({_fmt_grams(round(water, 1))}g)\n"
        if salt > 0:
            result += f"  Salt:   {salt_pct:.1f}% ({_fmt_grams(salt)}g)\n"
        if yeast > 0:
            result += f"  Yeast:  {yeast_pct:.1f}% ({_fmt_grams(yeast)}g)\n"
        if sugar > 0:
            result += f"  Sugar:  {sugar_pct:.1f}% ({_fmt_grams(sugar)}g)\n"
        if fat > 0:
            result += f"  Fat:    {fat_pct:.1f}% ({_fmt_grams(fat)}g)\n"
        if other > 0:
            result += f"  Other:  {other_pct:.1f}% ({_fmt_grams(other)}g)\n"
        for name, grams in extras.items():
            if grams > 0:
                result += f"  {name}:  {grams / flour * 100:.1f}% ({_fmt_grams(grams)}g)\n"

        result += f"\n  Total:  {total_pct:.1f}% ({_fmt_grams(round(total_weight, 1))}g)\n"

        # Add hydration note if water is present
        if water > 0:
            result += (
                f"\n  Hydration = water ÷ flour × 100"
                f"\n            = {_fmt_grams(round(water, 1))} ÷ {_fmt_grams(flour)} × 100"
                f" = {water_pct:.1f}%"
            )
            if water_pct < 50:
                result += " (stiff dough)"
            elif water_pct < 65:
                result += " (medium dough)"
            elif water_pct < 80:
                result += " (soft/wet dough)"
            else:
                result += " (very wet/batter)"
            if extras:
                result += "\n  (Hydration counts the water weight only; other liquids are listed separately.)"

        return result

    except Exception as e:
        return f"Baker's percentage calculation error: {str(e)}"


# Tool definitions for OpenAI function calling
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current real-time date and time with timezone information. Use this WHENEVER the user asks about the current time, date, day of week, or what time it is. Common phrases: 'what time is it', 'what's the time', 'current time', 'what day is it', 'what's today's date', 'tell me the time', etc. Always use this tool instead of relying on any stored time information.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get current real-time weather information for any location. Use this WHENEVER the user asks anything about weather, temperature, climate, conditions, forecast, or how it is outside. Common phrases: 'what is the weather like', 'how's the weather', 'is it raining', 'weather today', 'temperature in', 'what's it like in', 'climate in', etc. This tool provides current temperature (Fahrenheit), feels-like temperature, conditions (sunny, cloudy, rainy, etc.), and humidity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city name or 'City, Country Code' (e.g., 'London', 'Paris, FR', 'New York, US', 'Barbados'). Extract the location from the user's query. If no location is mentioned, use 'New York'."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_recipes",
            "description": "Search for a specific recipe online. ONLY use this when the user explicitly asks for a recipe with a specific dish name. Trigger phrases: 'find me a recipe for...', 'give me a recipe for...', 'recipe for...', 'how do I make [specific dish]'. Do NOT use this for general questions, suggestions, advice, menu ideas, or discussions about food. If the user asks 'what dessert should I add to my menu' or 'what goes well with X', just answer conversationally without searching.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The recipe search term extracted from the user's request (e.g., 'chocolate cake', 'gluten free cookies', 'brownies', 'chicken'). Keep it simple - just the main dish or dessert name."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of recipes to return (default: 3, max: 5). Use 1 for specific requests, 3 for general searches.",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "convert_units",
            "description": "Convert between baking measurement units (cups, grams, ounces, tablespoons, teaspoons, milliliters, pounds). Accounts for ingredient-specific density. Use this whenever the user asks to convert measurements or asks 'how many grams in X cups' or similar. Common phrases: 'convert X cups to grams', 'how many ounces in', 'grams to cups', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": "The numeric amount to convert (e.g., 2 for '2 cups')"
                    },
                    "from_unit": {
                        "type": "string",
                        "description": "Source unit: cups, grams, ounces, tbsp, tsp, ml, pounds",
                        "enum": ["cups", "grams", "ounces", "tbsp", "tsp", "ml", "pounds", "cup", "gram", "ounce", "tablespoons", "teaspoons", "milliliters", "lb"]
                    },
                    "to_unit": {
                        "type": "string",
                        "description": "Target unit: cups, grams, ounces, tbsp, tsp, ml, pounds",
                        "enum": ["cups", "grams", "ounces", "tbsp", "tsp", "ml", "pounds", "cup", "gram", "ounce", "tablespoons", "teaspoons", "milliliters", "lb"]
                    },
                    "ingredient": {
                        "type": "string",
                        "description": "Type of ingredient for accurate density conversion (e.g., 'flour', 'sugar', 'butter', 'cocoa powder', 'honey', 'milk', 'water', 'oil'). Use 'generic' if not specified.",
                        "default": "generic"
                    }
                },
                "required": ["value", "from_unit", "to_unit"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scale_recipe",
            "description": "Scale a recipe's ingredient quantities from original servings to desired servings. Use when user asks to 'scale up/down a recipe', 'double the recipe', 'make it for more people', 'adjust servings', etc. Multiplies all ingredient amounts proportionally.",
            "parameters": {
                "type": "object",
                "properties": {
                    "original_servings": {
                        "type": "integer",
                        "description": "Original number of servings the recipe makes"
                    },
                    "desired_servings": {
                        "type": "integer",
                        "description": "Desired number of servings needed"
                    },
                    "ingredients_text": {
                        "type": "string",
                        "description": "List of ingredients with amounts, separated by newlines or commas. Example: '2 cups flour, 1 cup sugar, 3 eggs, 1/2 tsp salt'"
                    }
                },
                "required": ["original_servings", "desired_servings", "ingredients_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_bakers_percentage",
            "description": "Calculate baker's percentages for bread and dough recipes. All ingredients expressed as percentages of flour weight (flour = 100%). Use when user asks about 'baker's percentage', 'hydration' (calculating it from flour and water weights, or finding the water needed for a target hydration), 'bread formula', or 'dough percentages'. Always use this tool for these calculations instead of computing by hand. Essential for professional bread baking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flour": {
                        "type": "number",
                        "description": "Weight of flour in grams (the base ingredient, always 100%)"
                    },
                    "water": {
                        "type": "number",
                        "description": "Weight of water in grams (for hydration calculation)",
                        "default": 0
                    },
                    "salt": {
                        "type": "number",
                        "description": "Weight of salt in grams",
                        "default": 0
                    },
                    "yeast": {
                        "type": "number",
                        "description": "Weight of yeast in grams",
                        "default": 0
                    },
                    "sugar": {
                        "type": "number",
                        "description": "Weight of sugar in grams",
                        "default": 0
                    },
                    "fat": {
                        "type": "number",
                        "description": "Weight of fat/butter/oil in grams",
                        "default": 0
                    },
                    "other": {
                        "type": "number",
                        "description": "Weight of other ingredients in grams",
                        "default": 0
                    },
                    "target_hydration": {
                        "type": "number",
                        "description": "Target hydration percentage (e.g. 70 for 70%). Use this when the user asks how much water is needed for a given hydration; leave water at 0 and the water weight is calculated."
                    },
                    "extra_ingredients": {
                        "type": "object",
                        "description": "Any additional named ingredients in grams, e.g. {\"eggs\": 100, \"milk\": 60, \"sourdough starter\": 120}. If several flours are used, add them together for the flour weight.",
                        "additionalProperties": {"type": "number"}
                    }
                },
                "required": ["flour"]
            }
        }
    }
]

# Map function names to actual functions
TOOL_FUNCTIONS = {
    "get_current_time": get_current_time,
    "get_current_weather": get_current_weather,
    "search_recipes": search_recipes,
    "convert_units": convert_units,
    "scale_recipe": scale_recipe,
    "calculate_bakers_percentage": calculate_bakers_percentage
}
