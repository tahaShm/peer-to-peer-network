from threading import Thread
from multiprocessing import Process
import time
from datetime import datetime
import socket
import random
from random import randrange

NODES  = 6
N = 3
BASE_PORT = 5000
PACKET_LOSS_PERCENTAGE = 5
MAIN_IP = "127.0.0.1"
BUFF_SIZE = 1024
THRESHOLD = 1000

SEND_DURATION = 2 #seconds
CHECK_NEIGHBOR_DURATION = 8 #seconds
TURN_ON_DURATION = 10 #seconds
TURN_OFF_DURATION = 20 #seconds

end_flag = False

def getPortFromId(id) : 
    return BASE_PORT + id
    
def getIPFromId(id) : 
    return MAIN_IP
    
def getInfoFromId(id) : 
    return [getIPFromId(id), getPortFromId(id)] #ip, port

def log_message(log_file, message):
    message += "\n"
    log_file.write(message)
    
class Node (Thread):
    def __init__(self, id, startTime, logFiles):
        Thread.__init__(self)
        
        self.logFiles = logFiles #connections - valid neighbors - availability - topology
        
        self.endFlag = False
        
        self.startTime = startTime
        self.lastSentTime = startTime
        
        self.id = id
        self.connections = list(range(NODES))
        self.port = getPortFromId(self.id)
        self.ip = MAIN_IP
        self.isdown = False
        self.isSearchingForNeighbor = False
        self.searchStartTime = startTime
        self.undiNeighbors = []
        self.bidiNeighbors = []
        self.tempNeighbor = -1
        self.lastSents = [startTime] * (NODES)
        self.lastReceives = [startTime] * (NODES)
        self.recvSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recvSock.bind((MAIN_IP, self.port))
        self.sendSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        #for logs
        self.recvCon = [0] * NODES #receives, sends
        self.sendCon = [0] * NODES #receives, sends
        
        self.bidStartTimes = []
        self.availableTimes = [0] * NODES
        
        self.topologies = [[0 for x in range(NODES)] for y in range(NODES)] 
        
    def logConnections(self, seconds) : 
        message = "At time : " + str(seconds) + "\n"
        for i in range(NODES) : 
            if (self.recvCon[i] != 0 or self.sendCon[i] != 0) :
                message = message +  "(Ip: " + MAIN_IP + ", Port: " + str(getPortFromId(i)) + ", Receives: " + str(self.recvCon[i]) + ", Sends: " + str(self.sendCon[i]) + ")\n"
        message = message + "____________________________________________________________________________________________\n"
        log_message(self.logFiles[0], message)
    
    def logValidNeighbors(self, seconds) : 
        message = "At time : " + str(seconds) + "\n"
        message = message + "( "
        for i in self.bidiNeighbors :
            message = message + str(i) + " " 
        message = message + ")\n"
        message = message + "____________________________________________________________________________________________\n"
        log_message(self.logFiles[1], message)
        
    def logAvailability(self, seconds) : 
        currentTime = datetime.now()
        message = "At time : " + str(seconds) + "\n"
        availList = list(range(NODES))
        availList.remove(self.id)
        for i in availList : 
            availSeconds = 0
            if (i in self.bidiNeighbors) : 
                for times in self.bidStartTimes : 
                    if (times[0] == i) : 
                        availInterval = currentTime - times[1]
                        availSeconds += availInterval.seconds + availInterval.microseconds * pow(10, -6)
                        break
            availRate = int((availSeconds + self.availableTimes[i]) / seconds * 100)
            message = message + "(" + "Node " + str(i) + ": " + str(availRate) + "%)\n"
        message = message + "____________________________________________________________________________________________\n"
        log_message(self.logFiles[2], message)
    
    def getConType(self, value) : 
        if (value == 1) : 
            return "uni"
        elif (value == 2) : 
            return "bi"
        else : 
            return "0"
        
        
    def logTopology(self, seconds) : 
        message = "At time : " + str(seconds) + "\n"
        
        for i in range(NODES) : 
            self.topologies[self.id][i] = 0
        for i in self.undiNeighbors : 
            self.topologies[self.id][i] = 1
        for i in self.bidiNeighbors : 
            self.topologies[self.id][i] = 2
            
        for i in range(NODES) : 
            message = message + "(Node" + str(i) + ": ["
            for j in range(NODES) : 
                message = message + self.getConType(self.topologies[i][j])
                if (j != NODES-1) : 
                    message = message + ", "
            message = message + "])\n"
        message = message + "____________________________________________________________________________________________\n"
        log_message(self.logFiles[3], message)
        
    
                
        
            
            
     
    def setEndFlag(self) : 
        self.endFlag = True
               
    def convertToStr(self, curList) : 
        result = ""
        for i in range(len(curList)) :
            info = getInfoFromId(curList[i])
            result += str(curList[i]) + "-" + info[0] + "-" + str(info[1])
            if (i < len(curList)-1) : 
                result += ","
        return result
          
    def sleep(self):
        self.isdown = True
    
    def wakeup(self):
        self.isdown = False
    
    def make_hello(self, reciever_id):
        message = str(self.id) + '|' + self.ip + '|' +  str(self.port) + "|hello_type|" + "neighbors:" + self.convertToStr(self.bidiNeighbors) + '|' + str(self.lastSents[reciever_id]) + '|' + str(self.lastReceives[reciever_id])
        return message.encode('utf-8')

    def send_hello(self, reciever_id):
        message = self.make_hello(reciever_id)
        rec_port = getPortFromId(reciever_id)
        
        self.lastSents[reciever_id] = datetime.now()
        
        self.sendSock.sendto(message, (getIPFromId(reciever_id), rec_port))
        
        self.sendCon[reciever_id] += 1
        
    def sendHelloToNeighbors(self) :
        # check whether bidirectional neigbors are sufficient
        self.checkSufficientNeighbors()
                 
        currentTime = datetime.now()
        interval = currentTime - self.lastSentTime
        if (interval.seconds >= SEND_DURATION and interval.seconds < THRESHOLD) :
            
            #connection log
            baseInterval = currentTime - self.startTime
            self.logConnections(baseInterval.seconds)
            
            #valid neighbors log
            self.logValidNeighbors(baseInterval.seconds)
            
            #availablility log
            self.logAvailability(baseInterval.seconds)
            
            #topology log
            self.logTopology(baseInterval.seconds)
            
            
            
            self.lastSentTime = currentTime
            for i in self.bidiNeighbors : 
                self.lastSents[i] = currentTime
                self.send_hello(i)
            if (self.isSearchingForNeighbor == True and self.tempNeighbor != -1) : 
                self.lastSents[self.tempNeighbor] = currentTime
                self.send_hello(self.tempNeighbor)
                
    def checkSufficientNeighbors(self) : 
        if (len(self.bidiNeighbors) < N and self.isSearchingForNeighbor == False) : 
            self.isSearchingForNeighbor = True
            self.searchStartTime = datetime.now()
            node_indexes = list(range(NODES))
            for i in self.bidiNeighbors : 
                node_indexes.remove(i)
            node_indexes.remove(self.id)
            randIdx = randrange(len(node_indexes))
            randIdx = node_indexes[randIdx]
            self.tempNeighbor = randIdx
            
             
            
            
                
    def checkForInactiveNeighbors(self) : 
        currentTime = datetime.now()
        inactiveBidiNeighbors = []
        
        # check bidi neighbors
        for i in range(len(self.bidiNeighbors)) : 
            id = self.bidiNeighbors[i]
            checkerInterval = currentTime - self.lastReceives[id]
            if (checkerInterval.seconds >= CHECK_NEIGHBOR_DURATION and checkerInterval.seconds < THRESHOLD) : 
                inactiveBidiNeighbors.append(id)
        
        for id in inactiveBidiNeighbors : 
            self.bidiNeighbors.remove(id)
            for times in self.bidStartTimes : 
                if (times[0] == id) : 
                    availableInterval = currentTime - times[1]
                    self.bidStartTimes.remove(times)
                    self.availableTimes[id] += availableInterval.seconds
            
        # check temp neighbor
        if (self.isSearchingForNeighbor == True and self.tempNeighbor != -1) : 
            checkerInterval = currentTime - self.searchStartTime
            if (checkerInterval.seconds >= CHECK_NEIGHBOR_DURATION and checkerInterval.seconds < THRESHOLD) : 
                self.isSearchingForNeighbor = False
                self.tempNeighbor = -1
        
    def getMessageInfo(self, message) : 
        words = message.split("|")
        return words
    
    def handleReceivePolicies(self, senderId, senderNeighbors) : 
        currentTime = datetime.now()
        if ((self.id) in senderNeighbors) : 
            if ((senderId not in self.bidiNeighbors) and len(self.bidiNeighbors) < N) : 
                self.bidiNeighbors.append(senderId)
                self.bidStartTimes.append([senderId, currentTime])
                # print("message from ", senderId, " to ", self.id, " -> ", senderId, " added to bidi")
                if (senderId in self.undiNeighbors) : 
                    self.undiNeighbors.remove(senderId)
                if (senderId == self.tempNeighbor) : 
                    self.tempNeighbor = -1
                    self.isSearchingForNeighbor = False
                    
            elif ((senderId not in self.bidiNeighbors) and len(self.bidiNeighbors) >= N) : 
                # print("message from ", senderId, " to ", self.id, " -> ", " added to uni because recv is full")
                if (senderId not in self.undiNeighbors) : 
                    self.undiNeighbors.append(senderId)
        
        else : 
            if (senderId == self.tempNeighbor and len(self.bidiNeighbors) < N) : 
                self.bidiNeighbors.append(senderId)
                self.bidStartTimes.append([senderId, currentTime])
                # print("message from ", senderId, " to ", self.id, " -> ", senderId, " added to bidi")
                if (senderId in self.undiNeighbors) : 
                    self.undiNeighbors.remove(senderId)
                self.tempNeighbor = -1
                self.isSearchingForNeighbor = False
                
            elif (senderId != self.tempNeighbor and (senderId not in self.undiNeighbors) and (senderId not in self.bidiNeighbors) and len(self.bidiNeighbors) < N) : 
                # print("message from ", senderId, " to ", self.id, " -> ", senderId, " added to bidi")
                self.bidiNeighbors.append(senderId)
                self.bidStartTimes.append([senderId, currentTime])
                
            elif (len(self.bidiNeighbors) >= N) : 
                if (senderId not in self.undiNeighbors) : 
                    self.undiNeighbors.append(senderId)
                # print("message from ", senderId, " to ", self.id, " -> ", " added to uni because recv is full")
            # else:
            #     print("message from ", senderId, " to ", self.id)
                
    
    def handleReceive(self, message) : 
        messageInfo = self.getMessageInfo(message)
        senderId = int(messageInfo[0])
        
        self.recvCon[senderId] += 1
        
        currentTime = datetime.now()
        self.lastReceives[senderId] = currentTime
        
        neighborPart = messageInfo[4]
        [n, neighbors] = neighborPart.split(":")
        neighbors = neighbors.split(",")
        senderNeighbors = []
        
        #new topology
        for i in range(NODES) : 
            self.topologies[senderId][i] = 0
        
        for neighbor in neighbors : 
            if (neighbor != "") : 
                senderNeighborInfo = neighbor.split("-")
                senderNeighborId = int(senderNeighborInfo[0])
                senderNeighbors.append(senderNeighborId)
                self.topologies[senderId][senderNeighborId] = 2
                self.topologies[senderNeighborId][senderId] = 2
                
        self.handleReceivePolicies(senderId, senderNeighbors)
        
    def receive_hello(self) :
        while (not self.endFlag):
            [message, address] = self.recvSock.recvfrom(BUFF_SIZE)
            if (self.isdown == False) :
                randNum = randrange(1, 101)
                if (randNum > PACKET_LOSS_PERCENTAGE) : 
                    message = message.decode()
                    self.handleReceive(message)
                
    
    def processActions(self) : 
        while (not self.endFlag):
            if (self.isdown == False) : 
                
                # sending hello to Neighbors every 2 seconds
                self.sendHelloToNeighbors()
                
                
                # checking for incative bidiNeighbors and temp neigbors to remove them in every 8 seconds with no message received       
                self.checkForInactiveNeighbors()
                
        for l in self.logFiles : 
            l.close()
        
        self.send_hello(self.id) # to end process
        
        
                
        
    def run(self):
        
        thread1 = Thread(target = self.processActions, args = ())
        thread1.start()
        
        thread2 = Thread(target = self.receive_hello, args = ())
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        
                    
                
            
            


print("program will run for 5 minutes ... ")
node_list = []
start_time = datetime.now()
if __name__ == '__main__':
    for i in range(NODES):
        logfile1 = open("node_" + str(i) + "_connections.txt", "w")
        logfile2 = open("node_" + str(i) + "_valid_neighbors.txt", "w")
        logfile3 = open("node_" + str(i) + "_availability.txt", "w")
        logfile4 = open("node_" + str(i) + "_topology.txt", "w")
        new_node = Node(i, start_time, [logfile1, logfile2, logfile3, logfile4])
        new_node.start()
        node_list.append(new_node)
    # running program for 1 minute.
    off_nodes = []
    prev_on_time = start_time
    while (True):
        passed_time = datetime.now() - start_time
        
        if ((passed_time.seconds//60)%60 == 5):
            break
        
        interval_on = datetime.now() - prev_on_time
        
        
        if (interval_on.seconds >= TURN_ON_DURATION) : 
            node_indexes = list(range(NODES))
            for i in off_nodes : 
                node_indexes.remove(i[0])
            randIdx = randrange(len(node_indexes))
            randIdx = node_indexes[randIdx]
            node_list[randIdx].sleep()
            prev_on_time = datetime.now()
            off_nodes.append([randIdx, prev_on_time])
        
        if (len(off_nodes) > 0) : 
            interval_off = datetime.now() - off_nodes[0][1]
            if (interval_off.seconds >= TURN_OFF_DURATION) : 
                firstOff = off_nodes.pop(0)
                node_list[firstOff[0]].wakeup()
                    
        

    for i in range(len(node_list)):
        node_list[i].setEndFlag()
        
    for i in range(len(node_list)):
        node_list[i].join()
    print ("Exiting Main Program")