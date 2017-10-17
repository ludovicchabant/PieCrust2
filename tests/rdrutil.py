from piecrust.rendering import RenderingContext, render_page


def render_simple_page(page):
    ctx = RenderingContext(page)
    rp = render_page(ctx)
    return rp.content

