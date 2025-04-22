# mojiweather_api/exceptions.py

class MojiWeatherAPIError(Exception):
    """Base exception for Moji Weather API related errors."""
    pass

class AuthenticationError(MojiWeatherAPIError):
    """Raised when API authentication fails."""
    pass

class InvalidLocationError(MojiWeatherAPIError):
    """Raised when the provided location is invalid or not found."""
    pass

class RequestFailedError(MojiWeatherAPIError):
    """Raised when an HTTP request fails."""
    pass

class ParsingError(MojiWeatherAPIError):
    """Raised when parsing HTML or JSON data fails."""
    pass

class HTMLStructureError(ParsingError):
    """Raised when expected elements are not found in the HTML structure."""
    pass

class JSONStructureError(ParsingError):
     """Raised when expected keys or structure are missing in the JSON data."""
     pass