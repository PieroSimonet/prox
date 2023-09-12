#!/usr/bin/env python3

import rospy
import math
import random

from std_msgs.msg import Header
from nav_msgs.msg import Path, Odometry
from geometry_msgs.msg import PoseStamped, Pose
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal, MoveBaseActionGoal
import actionlib
# from tf import TransformListener
import tf2_ros
import tf2_geometry_msgs

odom_topic = '/odom'
frame_destinatin = 'wcias_base_footprint'
goal_topic = '/move_base/goal/'

navigation_name = "move_base"

def odom_callback(data: Odometry):
    global odom_position
    odom_position = data

def goal_callback(data):
    global current_destination
    current_destination = data.goal.target_pose

def setup_listeners():
    rospy.Subscriber(odom_topic, Odometry, odom_callback)
    rospy.Subscriber(goal_topic, MoveBaseActionGoal, goal_callback)

def init_globals():
    global tf_buffer, tf_listener, current_destination, path, odom_position, state
    state = 0
    odom_position = Odometry()
    path = Path()
    
    tf_buffer = tf2_ros.Buffer()
    tf_listener = tf2_ros.TransformListener(tf_buffer)
    
    current_destination = PoseStamped()
    current_destination.header.frame_id = "wcias_odom"

def callback_bci(data):
    global state
    if (data > 0.7):
        state = 1
    elif(data < 0.3):
        state = -1
    else:
        state = 0

def set_controller_state():
    global odom_position, current_destination, movebase_client, tf_buffer, state

    d = math.sqrt( (odom_position.pose.pose.position.x - current_destination.pose.position.x) **2 +\
                   (odom_position.pose.pose.position.y - current_destination.pose.position.y) **2 )

    print(d)
    if d < 0.5:
        transform = tf_buffer.lookup_transform("wcias_odom", frame_destinatin, rospy.Time(0), rospy.Duration(1) )

        pose = PoseStamped()
        pose.header.frame_id = frame_destinatin

        # TODO: update this according to the bci signal
        
        pose.pose.position.x = 1
        #callback_bci(random.random())
        pose.pose.position.y = state

        pose = tf2_geometry_msgs.do_transform_pose(pose, transform)
        

        print("New destination")
        print(pose)

        # Send the command that is reached
        goal = MoveBaseGoal()
        goal.target_pose.pose = pose.pose
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.header.frame_id = "wcias_odom"

        movebase_client.send_goal(goal)



def main():
    rospy.init_node('bci_sender')

    global movebase_client
    movebase_client = actionlib.SimpleActionClient(navigation_name, MoveBaseAction)
    movebase_client.wait_for_server()

    init_globals()
    setup_listeners()

    # TODO : update these as parameters
    rate = rospy.Rate(16)

    while not rospy.is_shutdown():
        set_controller_state()
        rate.sleep()
    
if __name__ == '__main__':
    main()
