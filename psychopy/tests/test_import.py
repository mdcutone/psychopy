import pytest
from psychopy.tests.utils import profiledImport


@pytest.mark.timing
def test_import_speed(timing):
    """
    Test the speed of importing various parts of psychopy
    """
    # define cases:
    # - import: Module to import
    # - maxtime: Maximum allowed time (s) for import on a mid-range PC, will be
    #   adjusted for system speed
    # - notouch: Modules which importing this module shouldn't touch
    cases = [
        {
            'import': "psychopy.experiment",
            'maxtime': 5,
            'notouch': [
                "psychopy.visual",
                "psychopy.sound",
                "psychopy.hardware"
            ]
        }
    ]

    for case in cases:
        # do a profiled import, with the time limit scaled by system speed (in
        # case the runners are having a bad day), unclamped so that it's also
        # tightened on fast machines
        profiledImport(
            ref=case['import'],
            maxtime=timing.scaled(case['maxtime'], clamp=False),
            notouch=case['notouch']
        )


if __name__ == "__main__":
    from psychopy.tests.timing import getTimingTolerance
    test_import_speed(getTimingTolerance())
