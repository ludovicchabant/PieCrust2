from flask import current_app, render_template, request
from flask.views import View
from .menu import get_menu_context


class FoodTruckView(View):
    template_name = 'index.html'
    requires_menu = True

    def render_template(self, context):
        if self.requires_menu:
            context = with_menu_context()
        return render_template(self.template_name, **context)

    def get_context(self):
        return None

    def dispatch_request(self):
        ctx = self.get_context()
        return render_template(ctx)


def with_menu_context(context=None):
    if context is None:
        context = {}
    context['menu'] = get_menu_context()
    with_base_data(context)
    return context


def with_base_data(context=None):
    if context is None:
        context = {}

    script_root = request.script_root or ''
    root_url = current_app.config.get('FOODTRUCK_ROOT_URL') or ''
    context['base_url'] = script_root + root_url
