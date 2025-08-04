import asyncio
from robokassa import Robokassa
from robokassa.hash import HashAlgorithm


async def main():
    # Initialize Robokassa client
    robokassa = Robokassa(
        merchant_login="your_merchant_login",
        password1="your_password1",
        password2="your_password2",
        algorithm=HashAlgorithm.md5,
        is_test=True,  # Set to False for production
    )

    try:
        # Execute recurring payment
        # previous_inv_id - ID of the previous successful payment
        # out_sum - amount to charge
        # inv_id - new invoice ID for this recurring payment
        result = await robokassa.execute_recurring_payment(
            previous_inv_id=12345,  # ID of the original successful payment
            out_sum=100.0,          # Amount to charge
            inv_id=67890,           # New invoice ID for this recurring payment
            description="Monthly subscription payment",
            email="customer@example.com",
            user_ip="192.168.1.1",
            shp_subscription_id="sub_123",  # Additional parameter
            shp_user_id="user_456",         # Additional parameter
        )

        print(f"Recurring payment executed successfully!")
        print(f"Payment URL: {result.url}")
        print(f"Merchant Login: {result.params.merchant_login}")
        print(f"Amount: {result.params.out_sum}")
        print(f"Invoice ID: {result.params.inv_id}")
        print(f"Description: {result.params.description}")
        print(f"Email: {result.params.email}")
        print(f"User IP: {result.params.user_ip}")
        print(f"Test Mode: {result.params.is_test}")
        print(f"Additional Params: {result.params.additional_params}")

    except Exception as e:
        print(f"Error executing recurring payment: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 