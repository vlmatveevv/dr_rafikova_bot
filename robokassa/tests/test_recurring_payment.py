import pytest
from unittest.mock import AsyncMock, MagicMock

from robokassa import Robokassa
from robokassa.hash import HashAlgorithm
from robokassa.types import RobokassaResponse


@pytest.fixture
def robokassa():
    return Robokassa(
        merchant_login="test_login",
        password1="test_pass1",
        password2="test_pass2",
        algorithm=HashAlgorithm.md5,
        is_test=True,
    )


@pytest.mark.asyncio
async def test_execute_recurring_payment_success(robokassa):
    """Test successful recurring payment execution"""
    
    # Mock the HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "OK"
    
    # Mock the HTTP client
    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = None
    mock_http.post.return_value = mock_response
    
    # Patch the _create_http method
    robokassa._create_http = lambda url: mock_http
    
    # Execute recurring payment
    result = await robokassa.execute_recurring_payment(
        previous_inv_id=123,
        out_sum=100.0,
        inv_id=456,
        description="Test recurring payment",
        email="test@example.com",
        user_ip="127.0.0.1",
        shp_test_param="test_value"
    )
    
    # Verify the result
    assert isinstance(result, RobokassaResponse)
    assert result.url == "https://auth.robokassa.ru/Merchant/Recurring"
    assert result.params.merchant_login == "test_login"
    assert result.params.out_sum == 100.0
    assert result.params.inv_id == 456
    assert result.params.description == "Test recurring payment"
    assert result.params.email == "test@example.com"
    assert result.params.user_ip == "127.0.0.1"
    assert result.params.is_test is True
    assert "shp_test_param" in result.params.additional_params


@pytest.mark.asyncio
async def test_execute_recurring_payment_error(robokassa):
    """Test recurring payment execution with error response"""
    
    # Mock the HTTP response with error
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ERROR InvoiceInvalidRecurringParametersException PreviousInvoiceID is incorrect or empty"
    
    # Mock the HTTP client
    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = None
    mock_http.post.return_value = mock_response
    
    # Patch the _create_http method
    robokassa._create_http = lambda url: mock_http
    
    # Execute recurring payment and expect exception
    with pytest.raises(Exception) as exc_info:
        await robokassa.execute_recurring_payment(
            previous_inv_id=123,
            out_sum=100.0,
            inv_id=456
        )
    
    assert "Recurring payment failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_recurring_payment_http_error(robokassa):
    """Test recurring payment execution with HTTP error"""
    
    # Mock the HTTP response with HTTP error
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    
    # Mock the HTTP client
    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = None
    mock_http.post.return_value = mock_response
    
    # Patch the _create_http method
    robokassa._create_http = lambda url: mock_http
    
    # Execute recurring payment and expect exception
    with pytest.raises(Exception) as exc_info:
        await robokassa.execute_recurring_payment(
            previous_inv_id=123,
            out_sum=100.0,
            inv_id=456
        )
    
    assert "Recurring payment failed with status 500" in str(exc_info.value)


def test_recurring_payment_signature_creation():
    """Test that signature is created correctly for recurring payment"""
    from robokassa.payment import LinkGenerator
    from robokassa.hash import Hash
    
    mock_hash = Hash(HashAlgorithm.md5)
    generator = LinkGenerator(mock_hash, "test_password")
    
    # Test signature creation with required parameters
    signature = generator._create_signature(
        merchant_login="test_login",
        out_sum=100.0,
        inv_id=456,
        additional_params={"shp_test": "value"}
    )
    
    assert signature.value is not None
    assert len(signature.value) > 0 