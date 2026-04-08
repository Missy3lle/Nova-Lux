"""
Agent Tools: Functions that the AI agent can call to get real-time information.
"""

import os
import time
import requests
from datetime import datetime, timedelta
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
    }
]

# Map function names to actual functions
TOOL_FUNCTIONS = {
    "get_current_time": get_current_time,
    "get_current_weather": get_current_weather,
    "search_recipes": search_recipes
}
