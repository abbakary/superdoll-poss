"""
Management command to test the visit count logic.
Verifies that visit count increments correctly for orders on different days.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from tracker.models import Customer, Vehicle, Order, Branch
from tracker.services import CustomerService, VehicleService

class Command(BaseCommand):
    help = 'Test visit count logic for orders on different dates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Delete test customer and orders before running test',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("\n" + "="*60))
        self.stdout.write(self.style.WARNING("VISIT COUNT LOGIC TEST"))
        self.stdout.write(self.style.WARNING("="*60 + "\n"))

        try:
            # Get or create test branch
            branch, _ = Branch.objects.get_or_create(
                name='Test Branch',
                defaults={'code': 'TEST', 'region': 'Testing'}
            )

            # Clean up if requested
            test_customer_name = 'Test Visit Count Customer'
            if options['clean']:
                self.stdout.write("Cleaning up existing test data...")
                customers = Customer.objects.filter(full_name=test_customer_name)
                for cust in customers:
                    Order.objects.filter(customer=cust).delete()
                    Vehicle.objects.filter(customer=cust).delete()
                    cust.delete()
                self.stdout.write(self.style.SUCCESS("✓ Cleanup complete\n"))

            # Create test customer
            self.stdout.write("Step 1: Creating test customer...")
            customer, created = CustomerService.create_or_get_customer(
                branch=branch,
                full_name=test_customer_name,
                phone='9876543210',
                email='test@example.com',
                customer_type='personal',
            )
            
            # Reset customer visit count to 0
            customer.total_visits = 0
            customer.last_visit = None
            customer.save(update_fields=['total_visits', 'last_visit'])
            self.stdout.write(self.style.SUCCESS(f"✓ Customer created: {customer.full_name}\n"))

            # Create test vehicle
            self.stdout.write("Step 2: Creating test vehicle...")
            vehicle = VehicleService.create_or_get_vehicle(
                customer=customer,
                plate_number='TEST123',
                make='Test',
                model='Vehicle',
                vehicle_type='Test'
            )
            self.stdout.write(self.style.SUCCESS(f"✓ Vehicle created: {vehicle.plate_number}\n"))

            # Test scenario: Create orders on different days and track visit count
            self.stdout.write("Step 3: Creating orders on different dates...")
            self.stdout.write("-" * 60)

            test_cases = [
                {"day_offset": 0, "orders_on_day": 1, "expected_visits": 1},
                {"day_offset": 0, "orders_on_day": 2, "expected_visits": 1},  # Same day, should stay at 1
                {"day_offset": 1, "orders_on_day": 1, "expected_visits": 2},
                {"day_offset": 2, "orders_on_day": 2, "expected_visits": 3},  # Multiple orders same day
                {"day_offset": 3, "orders_on_day": 1, "expected_visits": 4},
            ]

            start_date = timezone.now() - timedelta(days=10)
            test_order_count = 0
            
            for test_case in test_cases:
                day_offset = test_case['day_offset']
                orders_on_day = test_case['orders_on_day']
                expected_visits = test_case['expected_visits']
                order_date = start_date + timedelta(days=day_offset)

                # Create orders on this day
                for order_num in range(orders_on_day):
                    # Create order
                    order = Order.objects.create(
                        order_number=Order()._generate_order_number(),
                        customer=customer,
                        vehicle=vehicle,
                        branch=branch,
                        type='service',
                        status='created',
                        priority='medium',
                        description=f'Test Order - Day {day_offset}, Order {order_num + 1}',
                        estimated_duration=60,
                        created_at=order_date,
                    )

                    # Call update_customer_visit to simulate normal order creation
                    CustomerService.update_customer_visit(customer)
                    
                    # Reload customer to get updated visit count
                    customer.refresh_from_db()
                    test_order_count += 1

                    # Display order info
                    visit_status = "✓" if customer.total_visits == expected_visits else "✗"
                    self.stdout.write(
                        f"{visit_status} Order {test_order_count}: "
                        f"Date: {order_date.strftime('%Y-%m-%d')}, "
                        f"Visits: {customer.total_visits}/{expected_visits}"
                    )

                # Verify visit count after processing all orders for this day
                if customer.total_visits == expected_visits:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Day {day_offset}: Visit count is correct ({expected_visits})\n"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ Day {day_offset}: Visit count mismatch! "
                            f"Expected {expected_visits}, got {customer.total_visits}\n"
                        )
                    )

            # Final verification
            self.stdout.write("="*60)
            self.stdout.write("FINAL RESULTS:")
            self.stdout.write("-" * 60)
            
            # Reload customer from database
            customer.refresh_from_db()
            orders = Order.objects.filter(customer=customer).order_by('created_at')
            
            # Count distinct days with orders
            order_dates = set()
            for order in orders:
                order_dates.add(order.created_at.date())
            
            distinct_days = len(order_dates)
            
            self.stdout.write(f"Total Orders Created: {orders.count()}")
            self.stdout.write(f"Distinct Days with Orders: {distinct_days}")
            self.stdout.write(f"Customer Total Visits (from DB): {customer.total_visits}")
            self.stdout.write(f"Customer Last Visit: {customer.last_visit.strftime('%Y-%m-%d') if customer.last_visit else 'None'}")

            # Determine if test passed
            if customer.total_visits == distinct_days:
                self.stdout.write(self.style.SUCCESS(
                    f"\n✓ TEST PASSED: Visit count ({customer.total_visits}) matches distinct days ({distinct_days})\n"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"\n✗ TEST FAILED: Visit count ({customer.total_visits}) does not match distinct days ({distinct_days})\n"
                ))

            # Show all orders
            self.stdout.write("Orders created:")
            for order in orders:
                self.stdout.write(f"  - {order.order_number}: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

            self.stdout.write(self.style.WARNING("="*60 + "\n"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Test error: {str(e)}"))
            import traceback
            traceback.print_exc()
