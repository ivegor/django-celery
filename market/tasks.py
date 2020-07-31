from datetime import timedelta

from django.db.models import Exists, OuterRef, Subquery, Q, DateTimeField
from django.db.models.functions import Coalesce
from django.utils import timezone

from elk.celery import app as celery
from market import signals
from market.models import Subscription, Class

UNUSED_GAP = timedelta(days=7)
NOTIFY_GAP = timedelta(days=1)


@celery.task
def notify_about_unused_subscription():
    for subscription in (
        Subscription.objects.filter(is_fully_used=False)
        .annotate(_exists_scheduled=Exists(Class.objects.scheduled().filter(subscription=OuterRef('pk'))))
        .exclude(_exists_scheduled=True)
        .annotate(_last_used_class=Coalesce(
            Subquery(Class.objects.used().order_by('-timeline__end').values('timeline__end')[:1]),
            'buy_date',
            output_field=DateTimeField())
        )
        .filter(_last_used_class__lt=timezone.now() - UNUSED_GAP)
        .filter(
            Q(last_notification_dt_about_unused__isnull=True) |
            Q(last_notification_dt_about_unused__lt=timezone.now() - NOTIFY_GAP)
        )
    ):
        subscription.last_notification_dt_about_unused = timezone.now()
        subscription.save(update_fields=('last_notification_dt_about_unused',))

        signals.unused_subscription.send(
            sender=subscription.__class__, crm=subscription.customer, instance=subscription
        )
