import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../bot')))
from db_client import DatabaseClient

class TestDatabaseClient(unittest.TestCase):
    @patch('db_client.create_engine')
    @patch('db_client.Base')
    @patch('db_client.sessionmaker')
    @patch('db_client.scoped_session')
    def test_initialization(self, mock_scoped_session, mock_sessionmaker, mock_base, mock_create_engine):
        # Setup mocks
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_session_factory = MagicMock()
        mock_sessionmaker.return_value = mock_session_factory
        mock_session = MagicMock()
        mock_scoped_session.return_value = mock_session

        # Initialize the database client
        db_client = DatabaseClient("sqlite:///test.db")

        # Verify method calls
        mock_create_engine.assert_called_once_with("sqlite:///test.db")
        mock_base.metadata.create_all.assert_called_once_with(mock_engine)
        mock_sessionmaker.assert_called_once_with(bind=mock_engine)
        mock_scoped_session.assert_called_once_with(mock_session_factory)

        # Verify attributes
        self.assertEqual(db_client._engine, mock_engine)
        self.assertEqual(db_client._session_factory, mock_session_factory)
        self.assertEqual(db_client._session, mock_session)

    @patch('db_client.create_engine')
    @patch('db_client.Base')
    @patch('db_client.sessionmaker')
    @patch('db_client.scoped_session')
    def test_get_session(self, mock_scoped_session, mock_sessionmaker, mock_base, mock_create_engine):
        # Setup mocks
        mock_session = MagicMock()
        mock_scoped_session.return_value = mock_session

        # Initialize the database client and get a session
        db_client = DatabaseClient("sqlite:///test.db")
        session = db_client.get_session()

        # Verify method calls
        mock_session.assert_called_once()

    @patch('db_client.create_engine')
    @patch('db_client.Base')
    @patch('db_client.sessionmaker')
    @patch('db_client.scoped_session')
    def test_close_session(self, mock_scoped_session, mock_sessionmaker, mock_base, mock_create_engine):
        # Setup mocks
        mock_session = MagicMock()
        mock_scoped_session.return_value = mock_session

        # Initialize the database client and close the session
        db_client = DatabaseClient("sqlite:///test.db")
        db_client.close_session()

        # Verify method calls
        mock_session.remove.assert_called_once()

    @patch('db_client.create_engine')
    @patch('db_client.Base')
    @patch('db_client.sessionmaker')
    @patch('db_client.scoped_session')
    def test_close(self, mock_scoped_session, mock_sessionmaker, mock_base, mock_create_engine):
        # Setup mocks
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_session = MagicMock()
        mock_scoped_session.return_value = mock_session

        # Initialize the database client and close
        db_client = DatabaseClient("sqlite:///test.db")
        db_client.close()

        # Verify method calls
        mock_session.remove.assert_called_once()
        mock_engine.dispose.assert_called_once()

if __name__ == '__main__':
    unittest.main()
