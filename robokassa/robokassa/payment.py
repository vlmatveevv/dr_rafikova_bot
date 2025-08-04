from collections.abc import Sequence
from typing import Any, Dict, Optional, Union
from urllib.parse import quote, urlencode

from robokassa.connection import Http
from robokassa.exceptions import RobokassaInterfaceError
from robokassa.hash import Hash
from robokassa.jwt import JWT
from robokassa.types import RobokassaParams, RobokassaResponse, Signature


class LinkGenerator:
    def __init__(self, hash: Hash, password_1: str) -> None:
        self._static_url = "https://auth.robokassa.ru/Merchant/Index.aspx"
        self._password = password_1
        self._hash = hash

    def _create_signature(
        self,
        merchant_login: Optional[str] = None,
        out_sum: Optional[Union[float, str, int]] = None,
        inv_id: Optional[Union[str | int]] = None,
        receipt: Optional[dict] = None,
        result_url2: Optional[str] = None,
        success_url2: Optional[str] = None,
        success_url2_method: Optional[str] = None,
        fail_url2: Optional[str] = None,
        fail_url2_method: Optional[str] = None,
        additional_params: Optional[Dict[str, int | str | float]] = None,
    ) -> Signature:
        return Signature(
            hash_=self._hash,
            merchant_login=merchant_login,
            out_sum=out_sum,
            inv_id=inv_id,
            receipt=receipt,
            result_url2=result_url2,
            success_url2=success_url2,
            success_url2_method=success_url2_method,
            fail_url2=fail_url2,
            fail_url2_method=fail_url2_method,
            password=self._password,
            additional_params=additional_params,
        )

    def _sort_url_params(
        self, urls: Dict[str, str], success_url_method: str, fail_url_method: str
    ) -> Dict[str, str]:
        urls_plus_methods = {}
        for k, v in urls.items():
            if v is not None:
                urls_plus_methods[k] = f"{v}"
                if k == "SuccessUrl2":
                    method = ["SuccessUrl2Method", success_url_method]
                elif k == "FailUrl2":
                    method = ["FailUrl2Method", fail_url_method]
                else:
                    method = None
                if method is not None:
                    urls_plus_methods[method[0]] = method[1]
        return urls_plus_methods

    def _get_serialized_link_to_payment_page(self, url_params: Dict[str, Any]) -> str:
        return f"{self._static_url}?{urlencode(url_params)}"

    def _serialize_url_params(
        self, params: RobokassaParams, additional: Sequence, ignore_names: Sequence = []
    ) -> dict:
        return {
            k: v
            for k, v in [
                ("MerchantLogin", params.merchant_login),
                ("OutSum", params.out_sum),
                ("InvId", params.inv_id),
                ("UserIp", params.user_ip),
                ("Receipt", params.receipt),
                ("Culture", params.culture),
                ("Description", params.description),
                ("ExpirationDate", params.expiration_date),
                ("Email", params.email),
                ("Recurring", "true" if params.recurring else False),
                *additional.items(),
                ("SignatureValue", params.signature_value),
                ("IsTest", int(params.is_test)),
            ]
            if k not in ignore_names
            and v
            and v != "null"
            or (isinstance(v, int) and v == 0)
        }

    def _assemble_url(self, params: RobokassaParams) -> str:
        additional_params_for_url = sorted(
            [f"{k}={v}" for k, v in params.additional_params.items()]
        )

        urls_plus_methods = self._sort_url_params(
            {
                "ResultUrl2": params.result_url,
                "SuccessUrl2": params.success_url,
                "FailUrl2": params.fail_url,
            },
            params.success_url_method,
            params.fail_url_method,
        )
        url_params = self._serialize_url_params(params, urls_plus_methods)

        url = (
            f"{self._get_serialized_link_to_payment_page(url_params)}"
            f"&{'&'.join(additional_params_for_url)}"
        )

        return url

    def _escape_link(self, link: str) -> str:
        return quote(link, safe="")

    def _to_camel_case(self, s: str) -> str:
        s = s.split("_")
        return "".join((i.capitalize() if i[0].islower() else i for i in s))

    def _create_header_jwt(self) -> dict:
        algorithm = self._hash.algorithm.value.upper()

        return {"typ": "JWT", "alg": algorithm}

    def generate_open_payment_link(self, params: RobokassaParams) -> RobokassaResponse:
        signature = self._create_signature(
            merchant_login=params.merchant_login,
            out_sum=params.out_sum,
            inv_id=params.inv_id,
            receipt=params.receipt,
            result_url2=params.result_url,
            success_url2=params.success_url,
            success_url2_method=params.success_url_method,
            fail_url2=params.fail_url,
            fail_url2_method=params.fail_url_method,
            additional_params=params.additional_params,
        )
        params.signature_value = signature.value

        return RobokassaResponse(url=self._assemble_url(params), params=params)

    def generate_subscription_payment_link(
        self, params: RobokassaParams
    ) -> RobokassaResponse:
        signature = self._create_signature(
            out_sum=params.out_sum,
            inv_id=params.inv_id,
            receipt=params.receipt,
            additional_params=params.additional_params,
        )
        params.signature_value = signature.value

        return RobokassaResponse(url=self._assemble_url(params), params=params)

    async def generate_protected_payment_link(
        self, http: Http, params: RobokassaParams
    ) -> RobokassaResponse:
        header = self._create_header_jwt()

        receipt = params.receipt.copy() if params.receipt else {}
        items = receipt.get("items") if receipt.get("items") else []

        payload = self._serialize_url_params(
            params,
            {
                "InvoiceType": params.invoice_type,
                "MerchantComments": params.merchant_comments,
                "InvoiceItems": [
                    {self._to_camel_case(k): v for k, v in item.items()}
                    for item in items
                ],
                "Sno": receipt.get("sno"),
            },
            ["Receipt"],
        )

        del payload["IsTest"]
        print(payload)
        signature = f"{params.merchant_login}:{self._password}"
        jwt = JWT(
            header=header, payload=payload, signature_key=signature, hash=self._hash
        ).create()

        async with http as conn:
            response = await conn.post("CreateInvoice", json=jwt)
            result = response.json()

            if result.get("isSuccess"):
                params.id = result["id"]
                return RobokassaResponse(url=result["url"], params=params)
            raise RobokassaInterfaceError("Failed to create link")

    async def deactivate_protected_payment_link(
        self,
        http: Http,
        merchant_login: str,
        encoded_id: Optional[str],
        id: Optional[str],
        inv_id: Optional[int],
    ) -> None:
        header = self._create_header_jwt()
        params = {
            "MerchantLogin": merchant_login,
            "InvId": inv_id,
            "Id": id,
            "EncodedId": encoded_id,
        }
        payload = {k: v for k, v in params.items() if v}
        signature = f"{merchant_login}:{self._password}"

        jwt = JWT(
            header=header, payload=payload, signature_key=signature, hash=self._hash
        ).create()

        async with http as conn:
            response = await conn.post("DeactivateInvoice", json=jwt)
            result = response.json()

            if not result.get("isSuccess"):
                raise RobokassaInterfaceError("Failed to deactivate invoice")

    async def execute_recurring_payment(
        self,
        http: Http,
        merchant_login: str,
        previous_inv_id: int,
        out_sum: Union[float, int],
        inv_id: int,
        receipt: Optional[dict] = None,
        description: Optional[str] = None,
        email: Optional[str] = None,
        user_ip: Optional[str] = None,
        is_test: bool = False,
        additional_params: Optional[Dict[str, Any]] = None,
    ) -> RobokassaResponse:
        """
        Execute recurring payment by sending POST request to Recurring endpoint.
        
        :param http: HTTP client instance
        :param merchant_login: Merchant login
        :param previous_inv_id: ID of the previous successful payment
        :param out_sum: Amount to charge
        :param inv_id: New invoice ID for this recurring payment
        :param receipt: Receipt data for fiscalization
        :param description: Payment description
        :param email: Customer email
        :param user_ip: Customer IP address
        :param is_test: Whether this is a test payment
        :param additional_params: Additional parameters
        :return: Response with payment details
        """
        
        if additional_params is None:
            additional_params = {}
            
        # Create signature for recurring payment
        signature = Signature(
            hash_=self._hash,
            merchant_login=merchant_login,
            out_sum=out_sum,
            inv_id=inv_id,
            receipt=receipt,
            password=self._password,
            additional_params=additional_params,
        )
        
        # Prepare form data for POST request
        form_data = {
            "MerchantLogin": merchant_login,
            "PreviousInvoiceID": previous_inv_id,
            "OutSum": out_sum,
            "InvId": inv_id,
            "SignatureValue": signature.value,
            "IsTest": int(is_test),
        }
        
        # Add optional parameters
        if receipt:
            form_data["Receipt"] = receipt
        if description:
            form_data["Description"] = description
        if email:
            form_data["Email"] = email
        if user_ip:
            form_data["UserIp"] = user_ip
            
        # Add additional parameters with shp_ prefix
        for key, value in additional_params.items():
            form_data[key] = value
            
        # Make POST request to Recurring endpoint
        async with http as conn:
            response = await conn.post("/Recurring", data=form_data)
            
            if response.status_code != 200:
                raise RobokassaInterfaceError(
                    f"Recurring payment failed with status {response.status_code}: {response.text}"
                )
                
            # Parse response - Robokassa returns XML for recurring payments
            response_text = response.text
            
            # Check if response contains error
            if "ERROR" in response_text.upper():
                raise RobokassaInterfaceError(f"Recurring payment failed: {response_text}")
                
            # For successful recurring payments, Robokassa typically redirects or returns success
            # We'll create a response object with the payment details
            params = RobokassaParams(
                merchant_login=merchant_login,
                out_sum=out_sum,
                inv_id=inv_id,
                receipt=receipt,
                description=description,
                email=email,
                user_ip=user_ip,
                is_test=is_test,
                additional_params=additional_params,
                signature_value=signature.value,
            )
            
            return RobokassaResponse(
                url=f"https://auth.robokassa.ru/Merchant/Recurring",
                params=params
            )
