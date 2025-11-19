from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response


@extend_schema(tags=["Health Endpoint"], summary="Health check")
@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})
