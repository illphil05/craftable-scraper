"""Parser registry — routes URLs to ATS-specific parsers."""
from .paylocity import parse as parse_paylocity
from .icims import parse as parse_icims
from .workday import parse as parse_workday
from .greenhouse import parse as parse_greenhouse
from .lever import parse as parse_lever
from .ukg import parse as parse_ukg
from .smartrecruiters import parse as parse_smartrecruiters
from .generic import parse as parse_generic

# URL pattern → parser function (first match wins, order matters)
PARSERS = [
    ("paylocity.com", parse_paylocity),
    ("icims.com", parse_icims),
    ("myworkday", parse_workday),
    ("workdayjobs", parse_workday),
    ("greenhouse.io", parse_greenhouse),
    ("lever.co", parse_lever),
    ("ultipro.com", parse_ukg),
    ("smartrecruiters.com", parse_smartrecruiters),
]


def get_parser(url: str):
    """Return the best parser for a URL, or generic as fallback."""
    url_lower = url.lower()
    for pattern, parser in PARSERS:
        if pattern in url_lower:
            return parser
    return parse_generic


def get_parser_name(url: str) -> str:
    """Return the name of the parser that would be selected."""
    url_lower = url.lower()
    for pattern, parser in PARSERS:
        if pattern in url_lower:
            return pattern.split('.')[0]
    return "generic"
