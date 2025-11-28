"""
Management command to seed sample started orders on different dates.
Creates a customer with 5 started orders spread across different days to test visit count logic.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from tracker.models import Customer, Vehicle, Order, Branch
from tracker.services import OrderService, CustomerService, VehicleService

class Command(BaseCommand):
    help = 'Create sample data: customer with 5 started orders on different dates'

    def handle(self, *args, **options):
        try:
            # Get or create a default branch
            branch, _ = Branch.objects.get_or_create(
                name='Default Branch',
                defaults={'code': 'DEFAULT', 'region': 'Central'}
            )
            self.stdout.write(f"Using branch: {branch.name}")

            # Create a sample customer
            customer_data = {
                'full_name': 'Multi-Day Customer',
                'phone': '1234567890',
                'email': 'multiday@example.com',
                'address': '123 Test Street',
                'customer_type': 'personal',
            }

            customer, created = CustomerService.create_or_get_customer(
                branch=branch,
                **customer_data
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created customer: {customer.full_name}"))
            else:
                self.stdout.write(f"Using existing customer: {customer.full_name}")

            # Create a vehicle
            vehicle = VehicleService.create_or_get_vehicle(
                customer=customer,
                plate_number='ABC123',
                make='Toyota',
                model='Camry',
                vehicle_type='Car'
            )
            self.stdout.write(f"Using vehicle: {vehicle.plate_number}")

            # Create 5 orders on different dates
            orders_created = 0
            customer.total_visits = 0  # Reset visit count
            customer.save(update_fields=['total_visits'])

            # Starting date (5 days ago)
            start_date = timezone.now() - timedelta(days=4)

            for day_offset in range(5):
                order_date = start_date + timedelta(days=day_offset)
                
                order_data = {
                    'customer': customer,
                    'vehicle': vehicle,
                    'branch': branch,
                    'type': 'service',
                    'status': 'created',
                    'priority': 'medium',
                    'description': f'Service Order - Day {day_offset + 1}',
                    'estimated_duration': 60 + (day_offset * 15),
                    'created_at': order_date,
                }

                # Create order directly to control created_at timestamp
                order = Order.objects.create(**order_data)

                # Manually update customer visit - simulating the normal flow
                # Set last_visit to the order date
                customer.last_visit = order_date
                customer.arrival_time = order_date
                customer.current_status = 'arrived'
                
                # Check if this is a new visit day
                last_visit_today = False
                if customer.last_visit:
                    try:
                        last_visit_date = customer.last_visit.date() if hasattr(customer.last_visit, 'date') else customer.last_visit
                        current_date = order_date.date() if hasattr(order_date, 'date') else order_date
                        # For this simulation, we want each day to be counted separately
                        last_visit_today = False  # Never true for our simulation
                    except Exception:
                        last_visit_today = False

                # Increment visit count for each day
                if not last_visit_today or day_offset == 0:
                    customer.total_visits = (customer.total_visits or 0) + 1

                customer.save(update_fields=['last_visit', 'total_visits', 'arrival_time', 'current_status'])

                orders_created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Order {orders_created}: {order.order_number} "
                        f"created on {order_date.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                )

            # Final customer state
            self.stdout.write(self.style.SUCCESS(f"\n✓ Customer final state:"))
            self.stdout.write(f"  - Name: {customer.full_name}")
            self.stdout.write(f"  - Total Visits: {customer.total_visits}")
            self.stdout.write(f"  - Last Visit: {customer.last_visit.strftime('%Y-%m-%d %H:%M:%S') if customer.last_visit else 'Never'}")
            self.stdout.write(f"  - Orders Created: {orders_created}")

            # Verify orders exist
            orders_count = Order.objects.filter(customer=customer).count()
            self.stdout.write(f"\nTotal orders for customer in database: {orders_count}")

            # Show all orders
            orders = Order.objects.filter(customer=customer).order_by('created_at')
            self.stdout.write(f"\nOrders created:")
            for order in orders:
                self.stdout.write(f"  - {order.order_number} on {order.created_at.strftime('%Y-%m-%d')}")

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Sample data created successfully!\n"
                    f"  Customer: {customer.full_name} (ID: {customer.id})\n"
                    f"  Vehicle: {vehicle.plate_number} (ID: {vehicle.id})\n"
                    f"  Visit Count: {customer.total_visits}\n"
                    f"  Orders: {orders_count}"
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error creating sample data: {str(e)}"))
            import traceback
            traceback.print_exc()
