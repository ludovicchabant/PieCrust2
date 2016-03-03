from piecrust.serving.server import WsgiServer


def get_app(root_dir, cache_key='prod', enable_debug_info=False):
    app = WsgiServer(root_dir,
                     cache_key=cache_key,
                     enable_debug_info=enable_debug_info)
    return app

