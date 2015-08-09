from piecrust.serving.server import WsgiServer


def get_app(root_dir, sub_cache_dir='prod', enable_debug_info=False):
    app = WsgiServer(root_dir,
                     sub_cache_dir=sub_cache_dir,
                     enable_debug_info=enable_debug_info)
    return app

