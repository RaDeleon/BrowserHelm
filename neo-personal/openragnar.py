"""Compatibility import for external pre-BrowserHelm scripts; new clients use browserhelm."""
from browserhelm import *
from browserhelm import BrowserHelmGateway as OpenRagnarGateway

if __name__ == '__main__':
    main()
