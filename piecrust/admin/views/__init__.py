from flask import render_template, current_app
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
    context['base_url'] = current_app.config['FOODTRUCK_URL_PREFIX']
