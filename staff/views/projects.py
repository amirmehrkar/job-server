from django.contrib import messages
from django.db import transaction
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, FormView, ListView, UpdateView, View

from jobserver.authorization import CoreDeveloper
from jobserver.authorization.decorators import require_role
from jobserver.authorization.utils import roles_for
from jobserver.models import Org, Project, ProjectMembership, User

from ..forms import ProjectAddMemberForm, ProjectEditForm


@method_decorator(require_role(CoreDeveloper), name="dispatch")
class ProjectAddMember(FormView):
    form_class = ProjectAddMemberForm
    template_name = "staff/project_membership_create.html"

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(Project, slug=self.kwargs["slug"])

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        roles = form.cleaned_data["roles"]
        users = form.cleaned_data["users"]

        with transaction.atomic():
            for user in users:
                self.project.memberships.create(
                    user=user,
                    created_by=self.request.user,
                    roles=roles,
                )

        return redirect(self.project.get_staff_url())

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            "members": self.project.members.order_by(Lower("username")),
            "project": self.project,
        }

    def get_form_kwargs(self):
        members = self.project.members.values_list("pk", flat=True)
        return super().get_form_kwargs() | {
            "available_roles": roles_for(ProjectMembership),
            "users": User.objects.exclude(pk__in=members),
        }

    def get_initial(self):
        return super().get_initial() | {
            "users": self.project.members.values_list("pk", flat=True),
        }


@method_decorator(require_role(CoreDeveloper), name="dispatch")
class ProjectDetail(DetailView):
    model = Project
    template_name = "staff/project_detail.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            "memberships": self.object.memberships.select_related("user").order_by(
                Lower("user__username")
            ),
            "workspaces": self.object.workspaces.order_by("name"),
        }


@method_decorator(require_role(CoreDeveloper), name="dispatch")
class ProjectEdit(UpdateView):
    form_class = ProjectEditForm
    model = Project
    template_name = "staff/project_edit.html"

    def get_form_kwargs(self):
        return super().get_form_kwargs() | {
            "users": User.objects.all(),
        }

    def get_success_url(self):
        return self.object.get_staff_url()


@method_decorator(require_role(CoreDeveloper), name="dispatch")
class ProjectList(ListView):
    queryset = Project.objects.select_related("org").order_by("name")
    template_name = "staff/project_list.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            "orgs": Org.objects.order_by("name"),
            "q": self.request.GET.get("q", ""),
        }

    def get_queryset(self):
        qs = super().get_queryset()

        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)

        org = self.request.GET.get("org")
        if org:
            qs = qs.filter(org__slug=org)
        return qs


@method_decorator(require_role(CoreDeveloper), name="dispatch")
class ProjectRemoveMember(View):
    def post(self, request, *args, **kwargs):
        project = get_object_or_404(Project, slug=self.kwargs["slug"])
        username = request.POST.get("username", None)

        try:
            project.memberships.get(user__username=username).delete()
        except ProjectMembership.DoesNotExist:
            pass

        messages.success(request, f"Removed {username} from {project.name}")

        return redirect(project.get_staff_url())
