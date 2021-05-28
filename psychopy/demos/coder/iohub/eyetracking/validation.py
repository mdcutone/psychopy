#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Example of performing eye tracker validation using the ioHub Common Eye Tracker interface
and the psychopy.iohub.client.eyetracker.validation.ValidationProcedure class.
"""
import time
from psychopy import visual
from psychopy import iohub
from psychopy.iohub.client.eyetracker.validation import TargetStim

if __name__ == "__main__":
    # Create a default PsychoPy Window
    # monitor *must* be the name of a valid PsychoPy Monitor config file.
    win = visual.Window((1920, 1080), fullscr=True, allowGUI=False, monitor='55w_60dist')

    # Create ioHub Server config ....
    sess_code = 'S_{0}'.format(int(time.mktime(time.localtime())))
    iohub_config = dict(experiment_code='validation_demo', session_code=sess_code)
    # Add an eye tracker device
    iohub_config['eyetracker.hw.mouse.EyeTracker'] = dict(name='tracker')

    # Start the ioHub process.
    io = iohub.launchHubServer(window=win, **iohub_config)

    # Get the eye tracker device.
    tracker = io.devices.tracker

    win.winHandle.set_fullscreen(False)
    win.winHandle.minimize()  # minimize the PsychoPy window

    # Run eyetracker calibration
    r = tracker.runSetupProcedure()

    win.winHandle.set_fullscreen(True)
    win.winHandle.maximize()  # maximize the PsychoPy window

    # ValidationProcedure setup

    # Create a target stim. iohub.client.eyetracker.validation.TargetStim provides a standard doughnut style
    # target. Or use any stim that has `.setPos()`, `.setRadius()`, and `.draw()` methods.
    target_stim = TargetStim(win, radius=0.025, fillcolor=[.5, .5, .5], edgecolor=[-1, -1, -1], edgewidth=2,
                             dotcolor=[1, -1, -1], dotradius=0.005, units='norm', colorspace='rgb')

    # target_positions: Provide your own list of validation positions,
    #target_positions = [(0.0, 0.0), (0.85, 0.85), (-0.85, 0.0), (0.85, 0.0), (0.85, -0.85), (-0.85, 0.85),
    #                    (-0.85, -0.85), (0.0, 0.85), (0.0, -0.85)]
    target_positions = 'FIVE_POINTS'

    # Create a validation procedure, iohub must already be running with an
    # eye tracker device, or errors will occur.
    validation_proc = iohub.ValidationProcedure(win,
                                          target=target_stim,  # target stim
                                          positions=target_positions,  # string constant or list of points
                                          randomize_positions=True,  # boolean
                                          expand_scale=2.0,  # float
                                          target_duration=1.25,  # float
                                          target_delay=1.0,  # float
                                          enable_position_animation=True,
                                          color_space=None,
                                          unit_type=None,
                                          progress_on_key=" ",  # str or None
                                          gaze_cursor=(-1.0, 1.0, -1.0),  # None or color value
                                          show_results_screen=False,  # bool
                                          save_results_screen=True,  # bool, only used if show_results_screen == True
                                          )

    # Run the validation procedure. run() does not return until the validation is complete.
    validation_proc.run()
    if validation_proc.results:
        results = validation_proc.results
        print("++++ Validation Results ++++")
        print("Passed:", results['passed'])
        print("failed_pos_count:", results['positions_failed_processing'])
        print("Units:", results['reporting_unit_type'])
        print("min_error:", results['min_error'])
        print("max_error:", results['max_error'])
        print("mean_error:", results['mean_error'])
    else:
        print("Validation Aborted by User.")
    io.quit()