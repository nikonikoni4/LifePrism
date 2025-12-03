import logging
import sys
import os

# Ensure the project root is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lifewatch.server.services.data_processing_service import DataProcessingService

# Configure logging to see the output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_data_processing_service():
    """
    Test DataProcessingService with hours=3 and use_incremental_sync=False
    """
    print("Starting test for DataProcessingService...")
    print("Parameters: hours=3, use_incremental_sync=False")
    
    try:
        # Initialize the service
        # Using default paths from config
        service = DataProcessingService()
        
        # Call the method with specified parameters
        # Setting auto_classify to False to focus on data processing logic
        result = service.process_activitywatch_data(
            hours=3,
            auto_classify=False,
            use_incremental_sync=True
        )
        
        print("\nTest completed successfully!")
        print("-" * 30)
        print("Result Summary:")
        for key, value in result.items():
            print(f"{key}: {value}")
        print("-" * 30)
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_data_processing_service()
