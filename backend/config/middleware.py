class PrivateAPIResponses:
    """User-specific API responses must not be reused by browser/shared caches."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(("/api/v1/users/", "/api/v1/ratings/", "/api/v1/recommendations/",
                                    "/api/v1/admin-panel/", "/api/v1/cinematography/tags/",
                                    "/api/v1/cinematography/moderation/")):
            response["Cache-Control"] = "private, no-store"
        return response
