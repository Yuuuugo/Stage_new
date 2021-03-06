import flwr as fl
import time 
import tensorflow.compat.v1 as tf
from copy import copy,deepcopy
from multiprocessing import Process
from federated.server.FedAvg import FedAvg
from federated.server.FedAdam import FedAdam
from federated.server.FedYogi import FedYogi
import pickle
from .client import Client
from model.model import FLModel

import tensorflow.compat.v1.keras.backend as K
tf.disable_v2_behavior()

"""
session = tf.compat.v1.Session(graph = tf.Graph() )
with session.graph.as_default():
  tf.keras.backend.set_session(session)
"""
class Federated():

    def __init__(self,model,dataset_name,data,strategy,nbr_clients,nbr_rounds,directory_name,
                 accumulated_data,loss, optimizer, metrics, graph):

          self.model = model
          self.dataset_name = dataset_name
          self.X_train = data.X_train
          self.X_test = data.X_test
          self.y_train = data.y_train
          self.y_test = data.y_test
          self.strategy = strategy
          self.nbr_clients = nbr_clients
          self.nbr_rounds = nbr_rounds
          self.directory_name = directory_name
          self.accumulated_data = accumulated_data
          self.loss = loss
          self.optimizer = optimizer
          self.metrics = metrics
          self.graph = graph 

    def start_server(self,model,):
        """
        Start a process for the server, call the class associated to the strategy
        """
        with tf.Session(graph= self.graph) as sess:
          K.set_session(sess)
          print("start server function")
          print("Server model loaded")
          #model = FLModel(self.dataset_name).model
          
          model = tf.keras.models.clone_model(self.model)
          model.compile(
            loss = self.loss,
            optimizer = self.optimizer,
            metrics = self.metrics
        )

          arguments = [model ,self.X_test,self.y_test ,self.nbr_clients, self.nbr_rounds, self.directory_name]
          server = eval(self.strategy)(*arguments)
    
    def start_client(self,X_train_client,y_train_client,model,client_nbr,):
        """
        Start a process for a single client with it associated dataset, dump the results in a pickle
        """
        
        with tf.Session(graph = self.graph) as sess:
          K.set_session(sess)
          print("Start client : " + str(client_nbr) )
          #model_client = FLModel(self.dataset_name).model
          model_client = tf.keras.models.clone_model(self.model)
          #print(model_client.__repr__() )
          model_client.compile(
              loss = self.loss,
              optimizer = self.optimizer,
              metrics = self.metrics
            )
          client = Client(
                model = model_client,
                X_train = X_train_client,
                y_train = y_train_client,
                X_test = self.X_test,
                y_test = self.y_test,
                client_nbr = client_nbr,
                nbr_rounds = self.nbr_rounds,
                accumulated_data = self.accumulated_data
                )
          print("client started")
          fl.client.start_numpy_client("[::]:8080", client = client)
          filename = self.directory_name + "/client_number_" + str(client_nbr) 
          with open(filename, "wb") as f:
            pickle.dump(client.metrics_list, f)

    def run(self):
        """
        Run the experience, with the server and each clients as a subprocess. The results will be dump in
        a pickle for each one
        """
        process = []
        model_server = tf.keras.models.clone_model(self.model)
        model_server.compile(
          loss = self.loss,
          optimizer = self.optimizer,
          metrics = self.metrics
        )
        
        server_process = Process(
                    target = self.start_server,
                    args = (model_server,),
                    )
        server_process.start()
        process.append(server_process)
        time.sleep(3)
        
        # Create partition for each client
        for i in range(self.nbr_clients):
            X_train_client = self.X_train[
                        int(( i / self.nbr_clients) * int(self.X_train.shape[0])) : 
                        int( ((i+1) / self.nbr_clients) * int(self.X_train.shape[0])) ]
                
            y_train_client = self.y_train[
                        int(( i / self.nbr_clients) * int(self.y_train.shape[0])) : 
                        int( ((i+1) / self.nbr_clients) * int(self.y_train.shape[0])) ]
            
            Client_i = Process(
                        target = self.start_client,
                        args = (X_train_client, y_train_client,self.model,i),
                        )
            Client_i.start()
            process.append(Client_i)
            
        for subprocess in process :
            subprocess.join()

