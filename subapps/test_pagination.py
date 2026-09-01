from django.core.paginator import Paginator
from django.test import RequestFactory, SimpleTestCase
from rest_framework.request import Request

from mainapps.profile.views import CompanyInvitationViewSet, StaffGroupViewSet, StaffRoleViewSet
from subapps.pagination import OptionalPageNumberPagination


class OptionalPageNumberPaginationTests(SimpleTestCase):
    def test_legacy_request_does_not_paginate(self):
        request = Request(RequestFactory().get("/management/roles/"))
        self.assertIsNone(OptionalPageNumberPagination().paginate_queryset(range(101), request))

    def test_page_response_contains_shared_metadata(self):
        request = Request(RequestFactory().get("/management/roles/?page=2&page_size=20"))
        pagination = OptionalPageNumberPagination()
        pagination.request = request
        pagination.page = Paginator(range(104), 20).page(2)

        response = pagination.get_paginated_response(["role"])

        self.assertEqual(response.data["count"], 104)
        self.assertEqual(response.data["page"], 2)
        self.assertEqual(response.data["page_size"], 20)
        self.assertEqual(response.data["total_pages"], 6)

    def test_staff_management_viewsets_opt_into_pagination(self):
        for viewset in (CompanyInvitationViewSet, StaffRoleViewSet, StaffGroupViewSet):
            self.assertIs(viewset.pagination_class, OptionalPageNumberPagination)
