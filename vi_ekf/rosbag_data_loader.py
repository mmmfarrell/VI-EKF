import csv
import numpy as np
import glob, os, sys
sys.path.append('/usr/local/lib/python2.7/site-packages')
import cv2
from tqdm import tqdm
from pyquat import Quaternion
from add_landmark import add_landmark
import yaml
import matplotlib.pyplot as plt
import rosbag
from mpl_toolkits.mplot3d import Axes3D
import scipy.signal

def to_list(vector3):
    return [vector3.x, vector3.y, vector3.z]

def to_list4(quat):
    return [quat.w, quat.x, quat.y, quat.z]

def load_from_file(filename):
    data = np.load(filename)
    return data.item()

def save_to_file(filename, data):
    np.save(filename, data)

def make_undistort_funtion(intrinsics, resolution, distortion_coefficients):
    A = np.array([[float(intrinsics[0]), 0., float(intrinsics[2])], [0., float(intrinsics[1]), float(intrinsics[3])], [0., 0., 1.]])
    Ap, _ = cv2.getOptimalNewCameraMatrix(A, distortion_coefficients, (resolution[0], resolution[1]), 1.0)

    def undistort(image):
        return cv2.undistort(image, A, distortion_coefficients, None, Ap)

    return undistort, Ap

def load_data(filename, start=0, end=np.inf, sim_features=False, show_image=False, plot_trajectory=False):
    # First, load IMU data
    bag = rosbag.Bag(filename)
    imu_data = []
    truth_pose_data = []

    for topic, msg, t in bag.read_messages(topics=['/imu/data',
                                                   '/vrpn_client_node/Leo/pose',
                                                   '/baro/data',
                                                   '/sonar/data',
                                                   '/is_flying',
                                                   '/gps/data',
                                                   '/mag/data']):

        if topic == '/imu/data':
            imu_meas = [msg.header.stamp.to_sec(),
                        msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z,
                        msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z]
            imu_data.append(imu_meas)

        if topic == '/vrpn_client_node/Leo/pose':
            truth_meas = [msg.header.stamp.to_sec(),
                          msg.pose.position.z, -msg.pose.position.x, -msg.pose.position.y,
                          -msg.pose.orientation.w, -msg.pose.orientation.z, msg.pose.orientation.x, msg.pose.orientation.y]
            truth_pose_data.append(truth_meas)

    imu_data = np.array(imu_data)
    truth_pose_data = np.array(truth_pose_data)

    # Remove Bad Truth Measurements
    good_indexes = np.hstack((True, np.diff(truth_pose_data[:,0]) > 1e-3))
    truth_pose_data = truth_pose_data[good_indexes]

    # Calculate body-fixed velocity by differentiating position and rotating
    # into the body frame
    inertial_vel = np.zeros(3)
    b, a = scipy.signal.butter(8, 0.03) # Create a Butterworth Filter
    # differentiate Position
    delta_x = np.diff(truth_pose_data[:,1:4], axis=0)
    delta_t = np.diff(truth_pose_data[:,0])
    unfiltered_inertial_velocity = np.vstack((np.zeros((1,3)), delta_x/delta_t[:,None]))
    # Filter
    v_inertial = scipy.signal.filtfilt(b, a, unfiltered_inertial_velocity, axis=0)
    # Rotate into Body Frame
    vel_data = []
    for i in range(len(truth_pose_data)):
        q_I_b = Quaternion(truth_pose_data[i,4:8,None])
        vel_data.append(q_I_b.rot(v_inertial[i,None].T).T)


    vel_data = np.array(vel_data).squeeze()
    ground_truth = np.hstack((truth_pose_data, vel_data))

    if plot_trajectory:
        plt.figure(2)
        ax = plt.subplot(111, projection='3d')
        plt.plot(truth_pose_data[:1, 1],
                 truth_pose_data[:1, 2],
                 truth_pose_data[:1, 3], 'kx')
        plt.plot(truth_pose_data[:, 1],
                 truth_pose_data[:, 2],
                 truth_pose_data[:, 3], 'c-')
        ax.set_xlabel('X axis')
        ax.set_ylabel('Y axis')
        ax.set_zlabel('Z axis')
        e_x = 0.1*np.array([[1., 0, 0]]).T
        e_y = 0.1*np.array([[0, 1., 0]]).T
        e_z = 0.1*np.array([[0, 0, 1.]]).T
        for i in range(len(truth_pose_data)/100):
            j = i*100
            origin = truth_pose_data[j, 1:4,None]
            x_end = origin + Quaternion(truth_pose_data[j, 4:8,None]).rot(e_x)
            y_end = origin + Quaternion(truth_pose_data[j, 4:8,None]).rot(e_y)
            z_end = origin + Quaternion(truth_pose_data[j, 4:8,None]).rot(e_z)
            plt.plot([origin[0, 0], x_end[0, 0]], [origin[1, 0], x_end[1, 0]], [origin[2, 0], x_end[2, 0]], 'r-')
            plt.plot([origin[0, 0], y_end[0, 0]], [origin[1, 0], y_end[1, 0]], [origin[2, 0], y_end[2, 0]], 'g-')
            plt.plot([origin[0, 0], z_end[0, 0]], [origin[1, 0], z_end[1, 0]], [origin[2, 0], z_end[2, 0]], 'b-')
        plt.show()

    # quit()

    # if sim_features:
    # Simulate Landmark Measurements
    landmarks = np.random.uniform(-25, 25, (2,3))
    feat_time, zetas, depths, ids = add_landmark(ground_truth, landmarks)

    # else:
    #     # Load Camera Data and calculate Landmark Measurements
    #     images0 = []
    #     images1 = []
    #     image_time = []
    #     csvfile = open(folder + '/cam0/data.csv', 'rb')
    #     reader = csv.reader(csvfile)
    #     for i, row in tqdm(enumerate(reader)):
    #         if i > 0:
    #             image_time.append((float(row[0]) - t0) / 1e9)
    #             images0.append(folder + '/cam0/data/' + row[1])
    #             images1.append(folder + '/cam1/data/' + row[1])
    #             if show_image:
    #                 cv2.imshow('image', cv2.imread(folder+'/cam0/data/' + row[1]))
    #                 print image_time[-1]
    #                 #cv2.waitKey(0)
    #     image_time = np.array(image_time)
    #     # images = np.array(images)
    #
    #     with open(folder + '/cam0/sensor.yaml', 'r') as stream:
    #         try:
    #             data = yaml.load(stream)
    #
    #             cam0_sensor = {
    #                 'resolution': np.array(data['resolution']),
    #                 'intrinsics': np.array(data['intrinsics']),
    #                 'rate_hz': data['rate_hz'],
    #                 'distortion_coefficients': np.array(data['distortion_coefficients']),
    #                 'body_to_sensor_transform': np.array(data['T_BS']['data']).reshape(
    #                     (data['T_BS']['rows'], data['T_BS']['cols']))
    #             }
    #
    #
    #         except yaml.YAMLError as exc:
    #             print(exc)
    #
    #     with open(folder + '/cam1/sensor.yaml', 'r') as stream:
    #         try:
    #             data = yaml.load(stream)
    #             cam1_sensor = {
    #                 'resolution': data['resolution'],
    #                 'intrinsics': data['intrinsics'],
    #                 'rate_hz': data['rate_hz'],
    #                 'distortion_coefficients': np.array(data['distortion_coefficients']),
    #                 'body_to_sensor_transform': np.array(data['T_BS']['data']).reshape(
    #                     (data['T_BS']['rows'], data['T_BS']['cols']))
    #             }
    #
    #         except yaml.YAMLError as exc:
    #             print(exc)

    # Adjust timestamp
    t0 = imu_data[0,0]
    imu_data[:,0] -= t0
    ground_truth[:,0] -= t0
    feat_time[:] -= t0

    # Chop Data
    imu_data = imu_data[(imu_data[:,0] > start) & (imu_data[:,0] < end), :]
    # if sim_features:
    for l in range(len(landmarks)):
        zetas[l] = zetas[l][(feat_time > start) & (feat_time < end)]
        depths[l] = depths[l][(feat_time > start) & (feat_time < end)]
    ids = ids[(feat_time > start) & (feat_time < end)]
    # else:
    #     images0 = [f for f, t in zip(images0, (image_time > start) & (image_time < end)) if t]
    #     images1 = [f for f, t in zip(images1, (image_time > start) & (image_time < end)) if t]
    #     image_time = image_time[(image_time > start) & (image_time < end)]
    ground_truth = ground_truth[(ground_truth[:, 0] > start) & (ground_truth[:, 0] < end), :]

    out_dict = dict()
    out_dict['imu'] = imu_data
    out_dict['truth'] = ground_truth
    # if sim_features:
    out_dict['feat_time'] = feat_time
    out_dict['zetas'] = zetas
    out_dict['depths'] = depths
    out_dict['ids'] = ids
    # else:
    #     out_dict['cam0_sensor'] = cam0_sensor
    #     out_dict['cam1_sensor'] = cam1_sensor
    #     out_dict['cam0_frame_filenames'] = images0
    #     out_dict['cam1_frame_filenames'] = images1
    #     out_dict['cam_time'] = image_time

    return out_dict



if __name__ == '__main__':
    data = load_data('data/truth_imu_flight.bag')
    print "done"
