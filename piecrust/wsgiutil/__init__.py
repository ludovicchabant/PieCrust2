from piecrust.serving.server import Server


def get_app(root_dir, sub_cache_dir='prod', enable_debug_info=False):
    server = Server(root_dir,
                    sub_cache_dir=sub_cache_dir,
                    enable_debug_info=enable_debug_info)
    app = server.getWsgiApp()
    return app

