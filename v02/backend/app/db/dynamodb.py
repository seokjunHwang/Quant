import aioboto3
from typing import Any

from app.config import Settings


class DynamoDBClient:
    """DynamoDB async client wrapper."""

    def __init__(self, session: aioboto3.Session, settings: Settings):
        self._session = session
        self._settings = settings
        self._resource = None

    @property
    def table_prefix(self) -> str:
        return self._settings.dynamodb_table_prefix

    def table_name(self, name: str) -> str:
        return f"{self.table_prefix}{name}"

    async def get_resource(self):
        if self._resource is None:
            kwargs = {"region_name": self._settings.aws_region}
            if self._settings.dynamodb_endpoint_url:
                kwargs["endpoint_url"] = self._settings.dynamodb_endpoint_url
            if self._settings.aws_access_key_id:
                kwargs["aws_access_key_id"] = self._settings.aws_access_key_id
                kwargs["aws_secret_access_key"] = self._settings.aws_secret_access_key
            self._resource = await self._session.resource("dynamodb", **kwargs).__aenter__()
        return self._resource

    async def table(self, name: str):
        resource = await self.get_resource()
        return await resource.Table(self.table_name(name))

    async def put_item(self, table_name: str, item: dict[str, Any]) -> None:
        tbl = await self.table(table_name)
        await tbl.put_item(Item=item)

    async def get_item(self, table_name: str, key: dict[str, Any]) -> dict | None:
        tbl = await self.table(table_name)
        response = await tbl.get_item(Key=key)
        return response.get("Item")

    async def query(
        self,
        table_name: str,
        key_condition: str,
        expression_values: dict,
        index_name: str | None = None,
        limit: int | None = None,
        scan_forward: bool = True,
    ) -> list[dict]:
        tbl = await self.table(table_name)
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": key_condition,
            "ExpressionAttributeValues": expression_values,
            "ScanIndexForward": scan_forward,
        }
        if index_name:
            kwargs["IndexName"] = index_name
        if limit:
            kwargs["Limit"] = limit

        items = []
        response = await tbl.query(**kwargs)
        items.extend(response.get("Items", []))

        while "LastEvaluatedKey" in response:
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            response = await tbl.query(**kwargs)
            items.extend(response.get("Items", []))
            if limit and len(items) >= limit:
                break

        return items[:limit] if limit else items

    async def batch_write(self, table_name: str, items: list[dict]) -> None:
        tbl = await self.table(table_name)
        async with tbl.batch_writer() as writer:
            for item in items:
                await writer.put_item(Item=item)

    async def close(self):
        if self._resource:
            await self._resource.__aexit__(None, None, None)
            self._resource = None


async def init_dynamodb(settings: Settings) -> DynamoDBClient:
    session = aioboto3.Session()
    return DynamoDBClient(session, settings)


async def close_dynamodb(client: DynamoDBClient) -> None:
    await client.close()
