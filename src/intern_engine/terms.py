"""What to ask a board's own search box for.

Several ATS only answer keyword searches, so the words we send decide what we
can ever see. These are the entry paths into IT the list is built around;
`filters_it` still judges every title that comes back.
"""

# Sent one at a time to boards that take a single phrase per request.
SEARCH_TERMS = ("help desk", "service desk", "desktop support", "IT support",
                "IT intern")
# For boards where we can afford only one request.
SINGLE_TERM = "IT support"
