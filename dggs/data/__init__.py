import os

HARNESS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
HARNESS_WINDOWS = r'C:\Users\{}\av'.format(os.environ['USER'])

# Convenience function
def join(*path):
    return os.path.join(HARNESS, *path)
