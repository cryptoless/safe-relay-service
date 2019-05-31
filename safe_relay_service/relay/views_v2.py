from logging import getLogger

from drf_yasg.utils import swagger_auto_schema
from hexbytes import HexBytes
from rest_framework import status
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from web3 import Web3

from gnosis.eth.constants import NULL_ADDRESS

from .models import SafeContract, SafeCreation2
from .serializers import (SafeCreation2ResponseSerializer,
                          SafeCreation2Serializer,
                          SafeCreationEstimateResponseSerializer,
                          SafeCreationEstimateV2Serializer,
                          SafeFunding2ResponseSerializer)
from .services.safe_creation_service import SafeCreationServiceProvider
from .tasks import deploy_create2_safe_task

logger = getLogger(__name__)


class SafeCreationEstimateView(CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = SafeCreationEstimateV2Serializer

    @swagger_auto_schema(responses={201: SafeCreationEstimateResponseSerializer(),
                                    400: 'Invalid data',
                                    422: 'Cannot process data'})
    def post(self, request, *args, **kwargs):
        """
        Estimates creation of a Safe
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            number_owners = serializer.data['number_owners']
            safe_creation_estimates = SafeCreationServiceProvider().estimate_safe_creation_for_all_tokens(number_owners)
            safe_creation_estimate_response_data = SafeCreationEstimateResponseSerializer(safe_creation_estimates,
                                                                                          many=True)
            return Response(status=status.HTTP_200_OK, data=safe_creation_estimate_response_data.data)
        else:
            return Response(status=status.HTTP_422_UNPROCESSABLE_ENTITY, data=serializer.errors)


class SafeCreationView(CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = SafeCreation2Serializer

    @swagger_auto_schema(responses={201: SafeCreation2ResponseSerializer(),
                                    400: 'Invalid data',
                                    422: 'Cannot process data'})
    def post(self, request, *args, **kwargs):
        """
        Begins creation of a Safe
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            salt_nonce, owners, threshold, payment_token = (serializer.data['salt_nonce'], serializer.data['owners'],
                                                            serializer.data['threshold'],
                                                            serializer.data['payment_token'])

            safe_creation_service = SafeCreationServiceProvider()
            safe_creation = safe_creation_service.create2_safe_tx(salt_nonce, owners, threshold, payment_token)
            safe_creation_response_data = SafeCreation2ResponseSerializer(data={
                'safe': safe_creation.safe.address,
                'master_copy': safe_creation.master_copy,
                'proxy_factory': safe_creation.proxy_factory,
                'payment': safe_creation.payment,
                'payment_token': safe_creation.payment_token or NULL_ADDRESS,
                'payment_receiver': safe_creation.payment_receiver or NULL_ADDRESS,
                'setup_data': HexBytes(safe_creation.setup_data).hex(),
                'gas_estimated': safe_creation.gas_estimated,
                'gas_price_estimated': safe_creation.gas_price_estimated,
            })
            safe_creation_response_data.is_valid(raise_exception=True)
            return Response(status=status.HTTP_201_CREATED, data=safe_creation_response_data.data)
        else:
            return Response(status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            data=serializer.errors)


class SafeSignalView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = SafeFunding2ResponseSerializer

    @swagger_auto_schema(responses={200: SafeFunding2ResponseSerializer(),
                                    404: 'Safe not found',
                                    422: 'Safe address checksum not valid'})
    def get(self, request, address, format=None):
        """
        Get status of the safe creation
        """
        if not Web3.isChecksumAddress(address):
            return Response(status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        else:
            try:
                safe_creation2 = SafeCreation2.objects.get(safe=address)
                serializer = self.serializer_class(safe_creation2)
                return Response(status=status.HTTP_200_OK, data=serializer.data)
            except SafeCreation2.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(responses={202: 'Task was queued',
                                    404: 'Safe not found',
                                    422: 'Safe address checksum not valid'})
    def put(self, request, address, format=None):
        """
        Force check of a safe balance to start the safe creation
        """
        if not Web3.isChecksumAddress(address):
            return Response(status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        else:
            try:
                SafeContract.objects.get(address=address)
            except SafeContract.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)

            deploy_create2_safe_task.delay(address)
            return Response(status=status.HTTP_202_ACCEPTED)