from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import FormView, ListView, UpdateView, View

from applications.form_specs import form_specs
from applications.models import Application
from applications.wizard import Wizard
from jobserver.authorization import CoreDeveloper
from jobserver.authorization.decorators import require_role
from jobserver.hash_utils import unhash_or_404

from ..forms import ApplicationApproveForm


@method_decorator(require_role(CoreDeveloper), name="dispatch")
class ApplicationApprove(FormView):
    form_class = ApplicationApproveForm
    model = Application
    template_name = "staff/application_approve.html"

    def dispatch(self, request, *args, **kwargs):
        self.application = get_object_or_404(
            Application, pk=unhash_or_404(self.kwargs["pk_hash"])
        )

        if not hasattr(self.application, "studyinformationpage"):
            msg = "The Study Information page must be filled in before an Application can be approved."
            messages.error(request, msg)
            return redirect(self.application.get_staff_url())

        if self.application.approved_at:
            return redirect(self.application.get_staff_url())

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        org = form.cleaned_data["org"]
        project_name = form.cleaned_data["project_name"]

        # create Project with the chosen org
        project = org.projects.create(name=project_name)

        self.application.approved_at = timezone.now()
        self.application.approved_by = self.request.user
        self.application.project = project
        self.application.save()

        return redirect(self.application.get_staff_url())

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            "application": self.application,
        }

    def get_initial(self):
        # set the value of project_name from the study_name field in the
        # application form
        return {"project_name": self.application.studyinformationpage.study_name}


@method_decorator(require_role(CoreDeveloper), name="dispatch")
class ApplicationDetail(View):
    def get(self, request, *args, **kwargs):
        application = get_object_or_404(
            Application, pk=unhash_or_404(self.kwargs["pk_hash"])
        )
        wizard = Wizard(application, form_specs)
        pages = [page.review_context() for page in wizard.get_pages()]

        ctx = {
            "application": application,
            "researchers": application.researcher_registrations.order_by("created_at"),
            "pages": pages,
        }

        return TemplateResponse(request, "staff/application_detail.html", ctx)

    def post(self, request, *args, **kwargs):
        application = get_object_or_404(
            Application, pk=unhash_or_404(self.kwargs["pk_hash"])
        )

        wizard = Wizard(application, form_specs)
        pages = list(wizard.get_pages())

        review_time = timezone.now()

        for page in pages:
            form = page.get_bound_approval_form(request.POST)
            if form.instance.pk and form.has_changed():
                form.instance.last_reviewed_at = review_time
                form.instance.reviewed_by = request.user
                form.save()

        return redirect("staff:application-detail", application.pk_hash)


@method_decorator(require_role(CoreDeveloper), name="dispatch")
class ApplicationEdit(UpdateView):
    fields = [
        "status",
        "status_comment",
    ]
    model = Application
    template_name = "staff/application_edit.html"

    def get_object(self):
        return get_object_or_404(
            Application,
            pk=unhash_or_404(self.kwargs["pk_hash"]),
        )

    def get_success_url(self):
        return self.object.get_staff_url()


@method_decorator(require_role(CoreDeveloper), name="dispatch")
class ApplicationList(ListView):
    model = Application
    ordering = "-created_at"
    template_name = "staff/application_list.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            "q": self.request.GET.get("q", ""),
            "statuses": Application.Statuses,
        }

    def get_queryset(self):
        qs = super().get_queryset()

        if q := self.request.GET.get("q"):
            qs = qs.filter(
                Q(created_by__first_name__icontains=q)
                | Q(created_by__last_name__icontains=q)
                | Q(created_by__username__icontains=q)
            )

        if status := self.request.GET.get("status"):
            qs = qs.filter(status=status)

        return qs
