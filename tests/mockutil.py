import mock
from piecrust.app import PieCrust, PieCrustConfiguration


def get_mock_app(config=None):
    app = mock.MagicMock(spec=PieCrust)
    app.config = PieCrustConfiguration()
    return app

