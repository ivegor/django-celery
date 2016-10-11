from datetime import datetime, timedelta
from unittest.mock import MagicMock

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone
from freezegun import freeze_time
from mixer.backend.django import mixer

from elk.utils.testing import TestCase, create_customer, create_teacher
from lessons import models as lessons
from market.models import Class
from timeline.models import Entry as TimelineEntry


@freeze_time('2005-05-03 12:41')
class EntryTestCase(TestCase):
    fixtures = ('crm',)

    def setUp(self):
        self.teacher1 = create_teacher()
        self.teacher2 = create_teacher()

    def test_entry_naming_simple(self):
        """
        """
        lesson = mixer.blend(lessons.OrdinaryLesson, name='Test_Lesson_Name')
        entry = mixer.blend(TimelineEntry, teacher=self.teacher1, lesson=lesson)
        self.assertIn('Test_Lesson_Name', str(entry))

    def test_entry_naming_with_student(self):
        lesson = mixer.blend(lessons.OrdinaryLesson, name='Test_Lesson_Name')
        entry = mixer.blend(TimelineEntry, teacher=self.teacher1, lesson=lesson, start=self.tzdatetime(2016, 2, 5, 3, 0))
        customer = create_customer()
        c = Class(
            customer=customer,
            lesson=lesson
        )
        c.assign_entry(entry)
        c.save()
        entry.refresh_from_db()
        self.assertIn(customer.full_name, str(entry))

    def test_default_scope(self):
        active_lesson = mixer.blend(lessons.OrdinaryLesson, name='Active_lesson')
        inactive_lesson = mixer.blend(lessons.OrdinaryLesson, name='Inactive_lesson')

        active_entry = mixer.blend(TimelineEntry, teacher=self.teacher1, lesson=active_lesson, active=1)
        inactive_entry = mixer.blend(TimelineEntry, teacher=self.teacher1, lesson=inactive_lesson, active=0)

        active_pk = active_entry.pk
        inactive_pk = inactive_entry.pk

        entries = TimelineEntry.objects.all().values_list('id', flat=True)
        self.assertIn(active_pk, entries)
        self.assertNotIn(inactive_pk, entries)

    def test_availabe_slot_count(self):
        event = mixer.blend(lessons.MasterClass, slots=10, host=self.teacher1)
        entry = mixer.blend(TimelineEntry, lesson=event, teacher=self.teacher1)
        entry.save()

        self.assertEqual(entry.slots, 10)

    def test_event_assigning(self):
        """
        Test if timeline entry takes all attributes from the event
        """
        lesson = mixer.blend(lessons.OrdinaryLesson)
        entry = mixer.blend(TimelineEntry, lesson=lesson, teacher=self.teacher1)

        self.assertEqual(entry.slots, lesson.slots)
        self.assertEqual(entry.end, entry.start + lesson.duration)

        self.assertEqual(entry.lesson_type, ContentType.objects.get(app_label='lessons', model='ordinarylesson'))

    def test_is_free(self):
        """
        Schedule a customer to a timeleine entry
        """
        lesson = mixer.blend(lessons.MasterClass, slots=10, host=self.teacher1)
        entry = mixer.blend(TimelineEntry, lesson=lesson, teacher=self.teacher1)
        entry.save()

        for i in range(0, 10):
            self.assertTrue(entry.is_free)
            self.assertEqual(entry.taken_slots, i)  # by the way let's test taken_slots count
            customer = create_customer()
            c = mixer.blend(Class, lesson_type=lesson.get_contenttype(), customer=customer)
            entry.classes.add(c)  # please don't use it in your code! use :model:`market.Class`.assign_entry() instead
            entry.save()

        self.assertFalse(entry.is_free)

        """ Let's try to schedule more customers, then event allows """
        with self.assertRaises(ValidationError):
            customer = create_customer()
            c = mixer.blend(Class, lesson_type=lesson.get_contenttype(), customer=customer)
            entry.classes.add(c)  # please don't use it in your code! use :model:`market.Class`.assign_entry() instead
            entry.save()

    def test_assign_entry_to_a_different_teacher(self):
        """
        We should not have possibility to assign an event with different host
        to someones timeline entry
        """
        lesson = mixer.blend(lessons.MasterClass, host=self.teacher1)

        with self.assertRaises(ValidationError):
            entry = mixer.blend(TimelineEntry, teacher=self.teacher2, lesson=lesson)
            entry.save()

    @freeze_time('2005-05-03 12:41')
    def test_entry_in_past(self):
        lesson = mixer.blend(lessons.MasterClass, host=self.teacher1)
        entry = mixer.blend(TimelineEntry, teacher=self.teacher1, lesson=lesson)
        entry.start = self.tzdatetime(2002, 1, 2, 3, 0)
        self.assertTrue(entry.is_in_past())

        entry.start = self.tzdatetime(2032, 12, 1)
        entry.end = entry.start + timedelta(minutes=30)
        self.assertFalse(entry.is_in_past())

    def test_to_be_marked_as_finished_queryset(self):
        lesson = mixer.blend(lessons.MasterClass, host=self.teacher1, duration='01:00:00')
        mixer.blend(TimelineEntry, teacher=self.teacher1, lesson=lesson, start=timezone.make_aware(datetime(2016, 12, 15, 15, 14)))

        TimelineEntry.objects._EntryManager__now = MagicMock(return_value=timezone.make_aware(datetime(2016, 12, 15, 17, 15)))
        self.assertEqual(TimelineEntry.objects.to_be_marked_as_finished().count(), 1)

        TimelineEntry.objects._EntryManager__now = MagicMock(return_value=timezone.make_aware(datetime(2016, 12, 15, 17, 13)))
        self.assertEqual(TimelineEntry.objects.to_be_marked_as_finished().count(), 0)  # two minutes in past this entry shoud not be marked as finished

    def test_dont_automaticaly_mark_finished_entries_as_finished_one_more_time(self):
        lesson = mixer.blend(lessons.MasterClass, host=self.teacher1, duration='01:00:00')
        entry = mixer.blend(TimelineEntry, teacher=self.teacher1, lesson=lesson, start=timezone.make_aware(datetime(2016, 12, 15, 15, 14)))

        TimelineEntry.objects._EntryManager__now = MagicMock(return_value=timezone.make_aware(datetime(2016, 12, 15, 17, 15)))
        entry.is_finished = True
        entry.save()
        self.assertEqual(TimelineEntry.objects.to_be_marked_as_finished().count(), 0)
