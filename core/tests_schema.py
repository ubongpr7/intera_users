import json

from django.test import SimpleTestCase


class OpenApiSchemaTests(SimpleTestCase):
    def test_swagger_json_is_generator_compatible(self):
        response = self.client.get("/swagger.json/", HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"].split(";")[0], "application/json")

        document = json.loads(response.content)
        self.assertEqual(document.get("swagger"), "2.0")
        operations = [
            operation
            for path_item in document.get("paths", {}).values()
            for operation in path_item.values()
            if isinstance(operation, dict) and "operationId" in operation
        ]
        self.assertGreater(len(operations), 0)
        self.assertEqual(len(operations), len({item["operationId"] for item in operations}))
