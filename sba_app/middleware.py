class NoCacheAuthMiddleware:
    """Prevents browsers from caching pages served to authenticated users.

    Without this, pressing the browser Back button after logout shows a
    stale cached copy of the dashboard instead of redirecting to login.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response
