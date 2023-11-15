import requests.exceptions

from django.urls import reverse_lazy
from django.views.generic.edit import FormView
from django.views.generic.base import TemplateView
from django.http import HttpResponseRedirect
from django.contrib import messages
from guardian.mixins import PermissionListMixin

from tom_tns.tns_report import send_tns_report, get_tns_report_reply,\
    BadTnsRequest
from tom_targets.models import Target, TargetName

import json


class TNSFormView(PermissionListMixin, TemplateView):
    template_name = 'tom_tns/tns_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target = Target.objects.get(pk=self.kwargs['pk'])
        context['target'] = target
        # We want to establish a default tab to display.
        # by default, we start on report, but change to classify if the target name starts with AT
        # If the target has an SN name, we warn the user that the target has likely been classified already.
        context['default_form'] = 'report'
        for name in target.names:
            if name.upper().startswith('AT'):
                context['default_form'] = 'classify'
            if name.upper().startswith('SN'):
                context['default_form'] = 'supernova'
                break
        return context


class TNSSubmitView(FormView):

    def get_success_url(self):
        return reverse_lazy('targets:detail', kwargs=self.kwargs)

    def form_invalid(self, form):
        messages.error(self.request, 'The following error was encountered when submitting to the TNS: '
                                     f'{form.errors.as_json()}')
        return HttpResponseRedirect(self.get_success_url())

    def form_valid(self, form):
        try:
            tns_report = form.generate_tns_report()
            report_id = send_tns_report(json.dumps(tns_report))
            iau_name = get_tns_report_reply(report_id, self.request)
            # update the target name
            if iau_name is not None:
                target = Target.objects.get(pk=self.kwargs['pk'])
                old_name = target.name
                target.name = iau_name
                target.save()
                new_alias = TargetName(name=old_name, target=target)
                new_alias.save()
        except (requests.exceptions.HTTPError, BadTnsRequest) as e:
            messages.error(self.request, f'TNS returned an error: {e}')
        return HttpResponseRedirect(self.get_success_url())
