from django.core import mail
from freezegun import freeze_time

from elk.utils.testing import create_customer, create_teacher, ClassIntegrationTestCase
from lessons import models as lessons
from market.models import Subscription
from market.tasks import notify_about_unused_subscription, UNUSED_GAP
from products.models import Product1


class TestNotifyAboutUnusedSubscriptionEmail(ClassIntegrationTestCase):
    fixtures = ('products', 'lessons')

    @classmethod
    def setUpTestData(cls):
        cls.customer = create_customer()
        cls.product = Product1.objects.get(pk=1)
        cls.date = cls.tzdatetime(2020, 7, 31, 10, 1)
        cls.lesson = lessons.OrdinaryLesson.get_default()
        cls.host = create_teacher(accepts_all_lessons=True, works_24x7=True)

    def setUp(self):
        self.subscription = Subscription(
            customer=self.customer,
            product=Product1.objects.get(pk=1),
            buy_date=self.date,
            buy_price=150,
        )
        self.subscription.save()
        self.class_ = self.customer.classes.first()
        self.entry = self._create_entry()

    def test_subscribe_wo_used_class_after_gap(self):
        with freeze_time(self.date + 2 * UNUSED_GAP):
            notify_about_unused_subscription()
            notify_about_unused_subscription()  # check to send 1 time

        self.assertEqual(len(mail.outbox), 1)

        out_emails = [outbox.to[0] for outbox in mail.outbox]
        self.assertIn(self.customer.user.email, out_emails)

    def test_subscribe_wo_used_class_before_gap(self):
        with freeze_time(self.date + 0.5 * UNUSED_GAP):
            notify_about_unused_subscription()

        self.assertEqual(len(mail.outbox), 0)

    def test_subscribe_used_last_class_after_gap(self):
        self.entry.start = self.date + 0.5 * UNUSED_GAP
        self.entry.save()
        self._schedule(self.class_, self.entry)
        self.class_.mark_as_fully_used()

        mail.outbox.clear()

        with freeze_time(self.date + 2 * UNUSED_GAP):
            notify_about_unused_subscription()
            notify_about_unused_subscription()  # check to send 1 time

        self.assertEqual(len(mail.outbox), 1)

        out_emails = [outbox.to[0] for outbox in mail.outbox]
        self.assertIn(self.customer.user.email, out_emails)

    def test_subscribe_used_last_class_before_gap(self):
        self.entry.start = self.date + 0.5 * UNUSED_GAP
        self.entry.save()
        self._schedule(self.class_, self.entry)
        self.class_.mark_as_fully_used()

        mail.outbox.clear()

        with freeze_time(self.date + 1 * UNUSED_GAP):
            notify_about_unused_subscription()

        self.assertEqual(len(mail.outbox), 0)

    def test_subscribe_class_add_to_schedule(self):
        self.entry.start = self.date + 2 * UNUSED_GAP
        self.entry.save()
        self._schedule(self.class_, self.entry)

        mail.outbox.clear()

        with freeze_time(self.date + 1.5 * UNUSED_GAP):
            notify_about_unused_subscription()

        self.assertEqual(len(mail.outbox), 0)
