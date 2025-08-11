import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from db_base import Base
from db_classes import RXPacket, TXPacket, ACK, MeshNodeDB

class DatabaseClient:
    """
    Database client class that handles all interactions with the database.
    This provides a layer of abstraction for database operations and error handling.
    """
    def __init__(self, connection_string):
        """
        Initialize the database client with a connection string

        Args:
            connection_string (str): SQLAlchemy connection string
        """
        self.connection_string = connection_string
        self._engine = None
        self._session_factory = None
        self._session = None
        self.initialize()

    def initialize(self):
        """Initialize the database connection and create tables if they don't exist"""
        try:
            self._engine = create_engine(self.connection_string)
            Base.metadata.create_all(self._engine)
            self._session_factory = sessionmaker(bind=self._engine)
            self._session = scoped_session(self._session_factory)
            logging.info("Database connection initialized successfully")
        except SQLAlchemyError as e:
            logging.error(f"Failed to initialize database connection: {str(e)}")
            raise

    def get_session(self):
        """Get a new session from the session factory"""
        return self._session()

    def close_session(self):
        """Close the current session"""
        if self._session:
            self._session.remove()

    def close(self):
        """Close all connections"""
        self.close_session()
        if self._engine:
            self._engine.dispose()

    def add_rx_packet(self, rx_packet):
        """Add a received packet to the database"""
        try:
            session = self.get_session()
            session.add(rx_packet)
            session.commit()
            return True
        except SQLAlchemyError as e:
            logging.error(f"Failed to add RX packet to database: {str(e)}")
            session.rollback()
            return False
        finally:
            session.close()

    def add_tx_packet(self, tx_packet):
        """Add a transmitted packet to the database"""
        try:
            session = self.get_session()
            session.add(tx_packet)
            session.commit()
            return True
        except SQLAlchemyError as e:
            logging.error(f"Failed to add TX packet to database: {str(e)}")
            session.rollback()
            return False
        finally:
            session.close()

    def add_ack(self, ack_packet):
        """Add an acknowledgement packet to the database"""
        try:
            session = self.get_session()
            session.add(ack_packet)
            session.commit()
            return True
        except SQLAlchemyError as e:
            logging.error(f"Failed to add ACK to database: {str(e)}")
            session.rollback()
            return False
        finally:
            session.close()

    def update_mesh_node(self, node_info):
        """Update or add a mesh node to the database"""
        try:
            session = self.get_session()
            node = session.query(MeshNodeDB).filter_by(node_id=node_info.node_id).first()

            if node:
                # Update existing node
                for key, value in node_info.__dict__.items():
                    if not key.startswith('_'):
                        setattr(node, key, value)
            else:
                # Add new node
                session.add(node_info)

            session.commit()
            return True
        except SQLAlchemyError as e:
            logging.error(f"Failed to update mesh node in database: {str(e)}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_active_nodes(self, minutes_ago):
        """Get all nodes that have been active in the last X minutes"""
        try:
            session = self.get_session()
            active_nodes = MeshNodeDB.get_active_nodes(session, minutes_ago)
            return active_nodes
        except SQLAlchemyError as e:
            logging.error(f"Failed to get active nodes: {str(e)}")
            return []
        finally:
            session.close()

    def get_all_nodes(self):
        """Get all nodes from the database"""
        try:
            session = self.get_session()
            all_nodes = session.query(MeshNodeDB).all()
            return all_nodes
        except SQLAlchemyError as e:
            logging.error(f"Failed to get all nodes: {str(e)}")
            return []
        finally:
            session.close()

    def get_node_by_id(self, node_id):
        """Get a node by its ID"""
        try:
            session = self.get_session()
            node = session.query(MeshNodeDB).filter_by(node_id=node_id).first()
            return node
        except SQLAlchemyError as e:
            logging.error(f"Failed to get node by ID: {str(e)}")
            return None
        finally:
            session.close()

    def get_node_by_name(self, node_name):
        """Get a node by its short name"""
        try:
            session = self.get_session()
            node = session.query(MeshNodeDB).filter_by(short_name=node_name).first()
            return node
        except SQLAlchemyError as e:
            logging.error(f"Failed to get node by name: {str(e)}")
            return None
        finally:
            session.close()

    def get_node_by_number(self, node_num):
        """Get a node by its number"""
        try:
            session = self.get_session()
            node = session.query(MeshNodeDB).filter_by(node_num=node_num).first()
            return node
        except SQLAlchemyError as e:
            logging.error(f"Failed to get node by number: {str(e)}")
            return None
        finally:
            session.close()

    def get_tx_packet(self, packet_id):
        """Get a TX packet by its ID"""
        try:
            session = self.get_session()
            packet = session.query(TXPacket).filter_by(packet_id=packet_id).first()
            return packet
        except SQLAlchemyError as e:
            logging.error(f"Failed to get TX packet: {str(e)}")
            return None
        finally:
            session.close()

    def update_tx_packet(self, packet_id, **kwargs):
        """Update a TX packet with the given attributes"""
        try:
            session = self.get_session()
            packet = session.query(TXPacket).filter_by(packet_id=packet_id).first()

            if packet:
                for key, value in kwargs.items():
                    if hasattr(packet, key):
                        setattr(packet, key, value)
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            logging.error(f"Failed to update TX packet: {str(e)}")
            session.rollback()
            return False
        finally:
            session.close()
