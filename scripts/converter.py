#!/usr/bin/env python3

import rospy
import math

from proximity_grid.msg import ProximityGridMsg
from std_msgs.msg import Header
from nav_msgs.msg import Path, Odometry
from geometry_msgs.msg import PoseStamped
from move_base_msgs.msg import MoveBaseActionGoal
from tf import TransformListener

from  std_srvs.srv import Empty 

odom_topic = '/odometry/filtered'
path_topic = '/move_base/TebLocalPlannerROS/local_plan' # here is necessary to put the path topic (global or local)
frame_destinatin = 'wcias_base_footprint'

goal_topic = "/move_base/goal"

def odom_callback(data: Odometry):
    global odom_position
    odom_position = data

def path_callback(data: Path):
    global path, current_destination
    path = data
    current_destination = path.poses[-1]

def goal_callback(data):
    global current_destination
    current_destination = data.goal.target_pose

def segment_path():
    global path, current_destination, odom_position
    # segment the path and update the current attractor 
    
    # TODO: update these as parameters
    n_distance = 2 # [m]
    delta_distance = 0.8 # [m]

    found = False

    for pose in path.poses[::-1]: # reverse the array in order to find the closest one
        d  = math.sqrt((pose.pose.position.x - odom_position.pose.pose.position.x)  ** 2 + (pose.pose.position.y - odom_position.pose.pose.position.y)  ** 2)
        dl = math.sqrt((pose.pose.position.x - current_destination.pose.position.x) ** 2 + (pose.pose.position.y - current_destination.pose.position.y) ** 2)
        # check witch is the first point that is closest to the current destination that accomplish the distance (reversing the path in order to find the closest one)
        if d < n_distance and dl > delta_distance and not found:
            current_destination = pose
            found = True
            break
    
    # if the path is empty set an attractor in the current odom position
    if not found:
        p = PoseStamped()
        p.pose = odom_position.pose.pose
        p.header.frame_id = "wcias_odom"
        current_destination = p
        

def generate_ranges(grid: ProximityGridMsg): 
    l = []
    global current_destination, tf, dest_pub

    # Get the current position in the odom frame, need to wait for the transform 
    now = rospy.Time(0)
    current_destination.header.stamp = now
    tf.waitForTransform(frame_destinatin, "wcias_odom", now, rospy.Duration(5.0))

    objective = tf.transformPose(frame_destinatin, current_destination )
    
    # Since we moved to the frame destination, the point are already referred to the current position in the odom frame
    d = math.sqrt(objective.pose.position.x ** 2 + objective.pose.position.y ** 2)
    alpha = math.atan2(objective.pose.position.y, objective.pose.position.x)

    # Setup the angle if the point is in the back position
    if alpha < grid.angle_min:
        alpha = grid.angle_min
    elif alpha > grid.angle_max:
        alpha = grid.angle_max 
    
    used = False

    n = int( (grid.angle_max - grid.angle_min) / grid.angle_increment )
    for i in range(n):
        if not used:
            if alpha >= grid.angle_min + i * grid.angle_increment and alpha < grid.angle_min + (i + 1) * grid.angle_increment:
                l.append(d)
                used = True
            else:
                l.append(float('inf'))
        else:
            l.append(float('inf'))  

    return l

def setup_listeners():
    rospy.Subscriber(odom_topic, Odometry, odom_callback)
    rospy.Subscriber(path_topic, Path, path_callback)
    rospy.Subscriber(goal_topic, MoveBaseActionGoal, goal_callback)

def setup_services():
    global start_srv, stop_srv
    rospy.wait_for_service("/navigation/navigation_start")
    rospy.wait_for_service("/navigation/navigation_stop")
    start_srv = rospy.ServiceProxy("/navigation/navigation_start", Empty)
    stop_srv  = rospy.ServiceProxy("/navigation/navigation_stop",  Empty)

def setup_grid(): 
    grid = ProximityGridMsg()
    angle_min = rospy.get_param('~angle_min', -2.09) # [rad]   
    angle_max = rospy.get_param('~angle_max',  2.09) # [rad]   
    angle_increment = rospy.get_param('~angle_increment', 0.16) # [rad] 
    range_min = rospy.get_param('~range_min', 0) # [m]   
    range_max = rospy.get_param('~range_max', 6) # [m] 
    frame_id = rospy.get_param('~frame_id', 'fused_scan') 
       
    grid.angle_min = angle_min   
    grid.angle_max = angle_max   
    grid.angle_increment = angle_increment 
    grid.range_min = range_min   
    grid.range_max = range_max

    return grid, frame_id

def init_globals():
    global tf, current_destination, path, odom_position
    odom_position = Odometry()
    path = Path()
    tf = TransformListener()
    current_destination = PoseStamped()
    current_destination.header.frame_id = "wcias_odom"


def set_controller_state():
    global odom_position, current_destination, dest_pub
    global start_srv, stop_srv
    global running

    d = math.sqrt( (odom_position.pose.pose.position.x - current_destination.pose.position.x) **2 +\
                   (odom_position.pose.pose.position.y - current_destination.pose.position.y) **2 )
    
    if (d > 0.2 and not running):
        start_srv()
        running = True
    elif d < 0.2 and running:
        stop_srv()
        # Set the current position as the destinatio, to remove proble of noise of the 
        #msg = MoveBaseActionGoal()
        
        #msg.goal.target_pose.pose = odom_position.pose.pose
        #msg.goal.target_pose.header = odom_position.header
        #dest_pub.publish(msg)
        current_destination.pose = odom_position.pose.pose
        running = False



def main():
    rospy.init_node('converter')
    pub = rospy.Publisher('attractors', ProximityGridMsg, queue_size=1)

    global running, tf, dest_pub
    dest_pub = rospy.Publisher('/move_base/goal', MoveBaseActionGoal, queue_size=1)

    running = False

    init_globals()
    grid, frame_id = setup_grid() 
    setup_listeners()
    setup_services()

    tf.waitForTransform(frame_destinatin, "wcias_odom", rospy.Time(), rospy.Duration(5.0))


    # TODO : update these as parameters
    rate = rospy.Rate(10)

    while not rospy.is_shutdown():
        head = Header()
        head.stamp = rospy.Time.now()
        head.frame_id = frame_id
        grid.header = head
        
        segment_path()
        grid.ranges = generate_ranges(grid)

        pub.publish(grid)

        set_controller_state()
        rate.sleep()
    
if __name__ == '__main__':
    main()
