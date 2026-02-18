from fastapi import Depends, Request

from app.config import Settings, get_settings


def get_dynamodb(request: Request):
    return request.app.state.dynamodb


def get_ws_manager(request: Request):
    return request.app.state.ws_manager


def get_config() -> Settings:
    return get_settings()
