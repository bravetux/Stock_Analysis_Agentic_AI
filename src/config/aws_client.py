# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import boto3
from src.config.settings import settings


def get_bedrock_session() -> boto3.Session:
    """
    Returns a boto3 Session with credentials for Bedrock.
    Supports temporary credentials (AWS_SESSION_TOKEN) for SSO / STS.
    """
    kwargs: dict = {"region_name": settings.aws_region}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    if settings.aws_session_token:
        kwargs["aws_session_token"] = settings.aws_session_token
    return boto3.Session(**kwargs)
