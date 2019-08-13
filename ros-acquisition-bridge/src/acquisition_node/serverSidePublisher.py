#!/usr/bin/env python

import rospy
from sensor_msgs.msg import CompressedImage, CameraInfo
from std_msgs.msg import Float32, Bool
import cPickle as pickle
import os
import Queue
import collections
import yaml
from duckietown_msgs.msg import WheelsCmdStamped


class publishingProcessor():
    """
    Processes the data coming from a remote device (Duckiebot or watchtower).
    """

    def __init__(self, logger):
        self.logger = logger
        self.logger.info("Setting up the server side process")

        self.requestImageSend = False

        self.ACQ_DEVICE_NAME = os.getenv('ACQ_DEVICE_NAME', "watchtower33")
        rospy.init_node('acquisition_node_'+self.ACQ_DEVICE_NAME)

        self.publisherImagesSparse = rospy.Publisher(
            "/"+self.ACQ_DEVICE_NAME+"/imageSparse/compressed", CompressedImage, queue_size=30)
        self.publisherMask = rospy.Publisher(
            "/"+self.ACQ_DEVICE_NAME+"/mask/compressed", CompressedImage, queue_size=1)
        self.publisherMaskNorm = rospy.Publisher(
            "/"+self.ACQ_DEVICE_NAME+"/maskNorm", Float32, queue_size=1)
        self.subscriberRawImage = rospy.Subscriber(
            '/'+self.ACQ_DEVICE_NAME+'/'+"requestImage", Bool, self.requestImage,  queue_size=1)
        self.publisherCameraInfo = rospy.Publisher(
            "/"+self.ACQ_DEVICE_NAME+"/camera_node/camera_info", CameraInfo, queue_size=30)
        self.logger.info(
            "Setting up the server side process completed. Waiting for messages...")

        self.IS_AUTOBOT = os.getenv("IS_AUTOBOT", False)
        if self.IS_AUTOBOT:
            self.ACQ_TOPIC_WHEEL_COMMAND = os.getenv(
                "ACQ_TOPIC_WHEEL_COMMAND", "wheels_driver_node/wheels_cmd")
            self.wheel_command_publisher = rospy.Publisher(
                '/'+self.ACQ_DEVICE_NAME+'/'+self.ACQ_TOPIC_WHEEL_COMMAND, WheelsCmdStamped, queue_size=20)

    def publishOnServer(self, outputDictQueue, inputDictQueue, quitEvent, logger):
        """
        Publishes the processed data on the ROS Master that the graph optimizer uses.
        """
        seq_stamper = 0

        # Run continuously, check for new data arriving from the acquisitionProcessor and processed it when it arrives
        while not quitEvent.is_set():
            try:
                newQueueData = outputDictQueue.get(block=False)
                incomingData = pickle.loads(newQueueData)
                if "imageStream" in incomingData:
                    imgMsg = incomingData["imageStream"]
                    imgMsg.header.seq = seq_stamper
                    self.publisherImagesSparse.publish(imgMsg)
                if "cameraInfo" in incomingData:
                    cameraInfo = incomingData["cameraInfo"]
                    self.publisherCameraInfo.publish(cameraInfo)
                if "maskNorm" in incomingData:
                    normMsg = incomingData["maskNorm"]
                    self.publisherMaskNorm.publish(normMsg)
                if "mask" in incomingData:
                    imgMsg = incomingData["mask"]
                    imgMsg.header.seq = seq_stamper
                    self.publisherMask.publish(imgMsg)
                if "wheels_cmd" in incomingData:
                    self.wheel_command_publisher.publish(
                        incomingData["wheels_cmd"])
                seq_stamper += 1

            except KeyboardInterrupt:
                raise(Exception("Exiting"))
            except Queue.Empty:
                pass
            except Exception as e:
                logger.warning("Exception: %s" % str(e))
                pass

            if self.requestImageSend:
                inputDict = dict()
                inputDict['requestImage'] = True
                if inputDict is not None:
                    inputDictQueue.put(obj=pickle.dumps(inputDict, protocol=-1),
                                       block=True,
                                       timeout=None)
                    self.requestImageSend = False
                self.logger.info("Request send")

    def requestImage(self, data):
        self.logger.info("Topic received")
        if data.data:
            self.requestImageSend = True
