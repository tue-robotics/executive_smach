import rospy

import traceback

import smach

__all__ = ['ConditionState']


class ConditionState(smach.State):
    """A state that will check a condition function a number of times.

    If max_checks > 1, it will block while the condition is false and once it
    has checked max_checks times, it will return false.
    """

    def __init__(self,
                 cond_cb,
                 input_keys=None,
                 output_keys=None,
                 poll_rate=rospy.Duration(0.05),
                 timeout=None,
                 max_checks=1):
        if input_keys is None:
            input_keys = []
        if output_keys is None:
            output_keys = []
        smach.State.__init__(self, outcomes=['true', 'false', 'preempted'], input_keys=input_keys,
                             output_keys=output_keys)

        self._cond_cb = cond_cb
        if hasattr(cond_cb, 'get_registered_input_keys') and hasattr(cond_cb, 'get_registered_output_keys'):
            self._cond_cb_input_keys = cond_cb.get_registered_input_keys()
            self._cond_cb_output_keys = cond_cb.get_registered_output_keys()
            self.register_input_keys(self._cond_cb_input_keys)
            self.register_output_keys(self._cond_cb_output_keys)
        self._poll_rate = poll_rate
        self._timeout = timeout
        self._max_checks = max_checks

    def execute(self, ud):
        start_time = rospy.Time.now()
        n_checks = 0
        outcome = 'false'

        while self._max_checks == -1 or n_checks <= self._max_checks:
            # Check for timeout
            if self._timeout and rospy.Time.now() - start_time > self._timeout:
                break
            # Check for preemption
            if self.preempt_requested():
                self.service_preempt()
                outcome = 'preempted'
                break
            # Call the condition
            try:
                if self._cond_cb(ud):
                    outcome = 'true'
                    break
            except:
                raise smach.InvalidUserCodeError("Error thrown while executing condition callback %s: " % str(
                    self._cond_cb) + traceback.format_exc())
            n_checks += 1
            rospy.sleep(self._poll_rate)

        if self.preempt_requested():
            self.service_preempt()
            outcome = 'preempted'
        return outcome
