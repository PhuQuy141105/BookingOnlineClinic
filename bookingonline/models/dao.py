import hashlib
from datetime import datetime, timedelta, date, time as dtime
from bookingonline import db
from bookingonline.models.models import *


def hash_password(password: str) -> str:
    return hashlib.md5(password.encode("utf-8")).hexdigest()

def get_user_by_username(username, role=None):
    q = User.query.filter_by(username=username)
    if role:
        q = q.filter_by(role=role)
    return q.first()

def verify_login(username, password, role=None):
    user = get_user_by_username(username, role)
    if user and user.password == password:
        return user
    return None

def create_patient_user(name, username, password, email, phone=None, gender=None):
    user = User(
        name=name, username=username, password=password,
        email=email, phone=phone, gender=gender,
        role=UserRoleEnum.PATIENT,
    )
    db.session.add(user)
    db.session.commit()
    return user

def get_system_config():
    config = SystemConfig.query.get(1)
    if not config:
        config = SystemConfig(
            id=1,
            minimumBookingTime=60,
            minimumCancellationTime=120,
            morningStartTime=dtime(7, 30),
            morningEndTime=dtime(11, 30),
            afternoonStartTime=dtime(13, 30),
            afternoonEndTime=dtime(17, 30),
            maxAppointmentsPerDay=1,
        )
        db.session.add(config)
        db.session.commit()
    return config

def get_all_specializations():
    return Specialization.query.order_by(Specialization.name).all()

def get_specialization_by_id(specialization_id):
    return Specialization.query.get(specialization_id)

def count_available_doctors(specialization_id):
    return (
        DoctorProfile.query
        .join(WorkSchedule, WorkSchedule.doctorId == DoctorProfile.id)
        .filter(
            DoctorProfile.specializationId == specialization_id,
            WorkSchedule.isAvailable == True,  # noqa: E712
            WorkSchedule.workDate >= date.today(),
        )
        .distinct()
        .count()
    )

def get_doctors_by_specialization(specialization_id):
    return DoctorProfile.query.filter_by(specializationId=specialization_id).all()

def get_doctor_by_id(doctor_id):
    return DoctorProfile.query.get(doctor_id)

def get_doctor_profile_by_user(user_id):
    return DoctorProfile.query.filter_by(userId=user_id).first()

def update_doctor_profile(profile, license_number, experience_yrs, fee, description=None, bio=None, avatar_url=None):
    profile.licenseNumber = license_number
    profile.experienceYrs = experience_yrs
    profile.fee = fee
    profile.description = description
    profile.bio = bio
    profile.avatarUrl = avatar_url
    db.session.commit()
    return profile

def get_available_work_schedules(doctor_id):
    today = date.today()
    monday_this_week = today - timedelta(days=today.weekday())
    end_date = monday_this_week + timedelta(days=13)
    return (
        WorkSchedule.query
        .filter(
            WorkSchedule.doctorId == doctor_id,
            WorkSchedule.isAvailable == True,
            WorkSchedule.workDate >= today,
            WorkSchedule.workDate <= end_date,
        )
        .order_by(WorkSchedule.workDate, WorkSchedule.startTime)
        .all()
    )


def split_time_range(start_time, end_time, slot_minutes=30):
    slots = []
    cur = datetime.combine(date.today(), start_time)
    end = datetime.combine(date.today(), end_time)
    while cur + timedelta(minutes=slot_minutes) <= end:
        slots.append((cur.time(), (cur + timedelta(minutes=slot_minutes)).time()))
        cur += timedelta(minutes=slot_minutes)
    return slots


def get_booked_times_for_doctor_date(doctor_id, work_date):
    rows = (
        Appointment.query
        .filter(
            Appointment.doctorId == doctor_id,
            Appointment.scheduledDate == work_date,
            Appointment.status == AppointmentStatusEnum.CONFIRMED,
        )
        .all()
    )
    return {r.scheduledTime for r in rows}


def get_available_slots_for_doctor(doctor_id, slot_minutes=30):
    blocks = get_available_work_schedules(doctor_id)
    slots = []
    booked_cache = {}
    for block in blocks:
        if block.workDate not in booked_cache:
            booked_cache[block.workDate] = get_booked_times_for_doctor_date(doctor_id, block.workDate)
        booked_times = booked_cache[block.workDate]

        for start_t, end_t in split_time_range(block.startTime, block.endTime, slot_minutes):
            if start_t in booked_times:
                continue
            slots.append({
                "work_schedule_id": block.id,
                "work_date": block.workDate,
                "session": block.session,
                "start": start_t,
                "end": end_t,
            })
    return slots


def is_slot_taken(doctor_id, work_date, work_time):
    return (
        Appointment.query
        .filter(
            Appointment.doctorId == doctor_id,
            Appointment.scheduledDate == work_date,
            Appointment.scheduledTime == work_time,
            Appointment.status == AppointmentStatusEnum.CONFIRMED,
        )
        .first() is not None
    )

def get_available_dates_for_doctor(doctor_id):
    schedules = get_available_work_schedules(doctor_id)
    seen = []
    for s in schedules:
        if s.workDate not in seen:
            seen.append(s.workDate)
    return seen

def get_work_schedules_for_doctor_on_date(doctor_id, work_date):
    return (
        WorkSchedule.query
        .filter(
            WorkSchedule.doctorId == doctor_id,
            WorkSchedule.workDate == work_date,
        )
        .order_by(WorkSchedule.startTime)
        .all()
    )

def get_work_schedule_by_id(work_schedule_id):
    return WorkSchedule.query.get(work_schedule_id)

def search_patient_profile(phone, name):
    return PatientHealthProfile.query.filter_by(phone=phone, name=name).first()


def get_patient_profiles_by_owner(user_id):
    return (
        PatientHealthProfile.query
        .filter_by(userId=user_id)
        .order_by(PatientHealthProfile.name)
        .all()
    )

def get_patient_profile_by_id(profile_id):
    return PatientHealthProfile.query.get(profile_id)

def create_patient_profile(owner, name, phone, gender=None, date_of_birth=None, address=None):
    profile = PatientHealthProfile(
        owner=owner,
        name=name,
        phone=phone,
        gender=gender,
        dateOfBirth=date_of_birth,
        address=address,
    )
    db.session.add(profile)
    db.session.commit()
    return profile

def get_patient_profile_by_owner(profile_id, user_id):
    return (
        PatientHealthProfile.query
        .filter(PatientHealthProfile.id == profile_id, PatientHealthProfile.userId == user_id)
        .first()
    )

def update_patient_profile(profile, name, phone, gender=None, date_of_birth=None, address=None):
    profile.name = name
    profile.phone = phone
    profile.gender = gender
    profile.dateOfBirth = date_of_birth
    profile.address = address
    db.session.commit()
    return profile

def find_conflicting_appointment(patient_profile_id, scheduled_date, scheduled_time):
    return (
        Appointment.query
        .filter(
            Appointment.patientProfileId == patient_profile_id,
            Appointment.scheduledDate == scheduled_date,
            Appointment.scheduledTime == scheduled_time,
            Appointment.status == AppointmentStatusEnum.CONFIRMED,
        )
        .first()
    )

def count_confirmed_appointments_on_date(patient_profile_id, scheduled_date):
    return (
        Appointment.query
        .filter(
            Appointment.patientProfileId == patient_profile_id,
            Appointment.scheduledDate == scheduled_date,
            Appointment.status == AppointmentStatusEnum.CONFIRMED,
        )
        .count()
    )

def create_appointment(patient_profile, doctor, work_schedule, scheduled_date,scheduled_time, reason, chatbot_suggestion=None):
    appointment = Appointment(
        patientProfile=patient_profile,
        doctor=doctor,
        workSchedule=work_schedule,
        scheduledDate=scheduled_date,
        scheduledTime=scheduled_time,
        status=AppointmentStatusEnum.CONFIRMED,
        reason=reason,
        chatbotSuggestion=chatbot_suggestion,
    )
    db.session.add(appointment)
    db.session.commit()
    return appointment


def create_pending_payment(appointment, amount):
    payment = Payment(
        appointment=appointment,
        amount=amount,
        status=PaymentStatusEnum.PENDING,
    )
    db.session.add(payment)
    db.session.commit()
    return payment


def save_payment_gateway_info(payment, transaction_id, checkout_url, qr_code):
    payment.transactionId = str(transaction_id)
    payment.checkoutUrl = checkout_url
    payment.qrCode = qr_code
    db.session.commit()
    return payment

def get_payment_by_id(payment_id):
    return Payment.query.get(payment_id)

def get_payment_by_transaction_id(transaction_id):
    return Payment.query.filter_by(transactionId=str(transaction_id)).first()

def confirm_payment_paid(payment):
    payment.status = PaymentStatusEnum.PAID
    payment.paidAt = datetime.now()
    db.session.commit()
    return payment

def mark_payment_failed(payment):
    payment.status = PaymentStatusEnum.FAILED
    db.session.commit()
    return payment

def is_payment_expired(payment, expire_minutes=15):
    if not payment or not payment.createdAt:
        return False
    return datetime.now() - payment.createdAt > timedelta(minutes=expire_minutes)

def cancel_pending_appointment(payment):
    appointment = payment.appointment
    db.session.delete(payment)
    if appointment:
        db.session.delete(appointment)
    db.session.commit()

def create_notification(user, title, body, ntype):
    notification = Notification(user=user, title=title, body=body, type=ntype)
    db.session.add(notification)
    db.session.commit()
    return notification

def get_unread_notification_count(user_id):
    return Notification.query.filter_by(userId=user_id, isRead=False).count()

def get_notifications_by_user(user_id, limit=10):
    return (
        Notification.query
        .filter_by(userId=user_id)
        .order_by(Notification.createdAt.desc())
        .limit(limit)
        .all()
    )

def get_appointment_by_id(appointment_id):
    return Appointment.query.get(appointment_id)

#--------------------ThaiHe---------------------
def get_doctors(keyword=None, specialization_id=None):
    query = (
        DoctorProfile.query
        .join(User, DoctorProfile.userId == User.id)
        .filter(
            User.role == UserRoleEnum.DOCTOR,
            User.active.is_(True)
        )
    )

    if keyword:
        keyword = keyword.strip()

        if keyword:
            query = query.filter(
                User.name.ilike(f"%{keyword}%")
            )

    if specialization_id:
        query = query.filter(
            DoctorProfile.specializationId == specialization_id
        )

    return query.order_by(User.name.asc()).all()

def get_doctor_detail(doctor_id):
    return (
        DoctorProfile.query
        .join(User, DoctorProfile.userId == User.id)
        .filter(
            DoctorProfile.id == doctor_id,
            User.role == UserRoleEnum.DOCTOR,
            User.active.is_(True)
        )
        .first()
    )

def get_reviews_by_doctor(doctor_id):
    return (
        Review.query
        .filter(Review.doctorId == doctor_id)
        .order_by(Review.time.desc())
        .all()
    )

def get_doctor_work_schedules_by_week(doctor_id, week_start):
    week_end = week_start + timedelta(days=6)

    return (
        WorkSchedule.query
        .filter(
            WorkSchedule.doctorId == doctor_id,
            WorkSchedule.workDate >= week_start,
            WorkSchedule.workDate <= week_end,
        )
        .order_by(
            WorkSchedule.workDate.asc(),
            WorkSchedule.startTime.asc()
        )
        .all()
    )

def get_week_start(target_date=None):
    target_date = target_date or date.today()

    return target_date - timedelta(
        days=target_date.weekday()
    )

def build_doctor_week_schedule(doctor_id, week_start):
    schedules = get_doctor_work_schedules_by_week(
        doctor_id,
        week_start
    )

    schedule_map = {}

    for schedule in schedules:
        schedule_map[
            (schedule.workDate, schedule.session)
        ] = schedule

    days = []

    for offset in range(7):
        current_date = week_start + timedelta(days=offset)

        days.append({
            "date": current_date,
            "morning": schedule_map.get(
                (
                    current_date,
                    WorkScheduleSessionEnum.MORNING
                )
            ),
            "afternoon": schedule_map.get(
                (
                    current_date,
                    WorkScheduleSessionEnum.AFTERNOON
                )
            )
        })

    return days

# Chatbot - bichnhu
WEEKDAY_CODE = {
    0: "MONDAY", 1: "TUESDAY", 2: "WEDNESDAY", 3: "THURSDAY",
    4: "FRIDAY", 5: "SATURDAY", 6: "SUNDAY",
}

def get_allowed_booking_dates(days_ahead=14):
    #các ngày được phép đặt lịch, dựa trên ngày làm việc
    #của phòng khám (SystemConfig.workingDays) và thời gian đặt tối thiểu.
    config = get_system_config()
    working_days = set(config.workingDaysList())
    today = date.today()
    now = datetime.now()
    result = []
    for i in range(days_ahead):
        d = today + timedelta(days=i)
        if WEEKDAY_CODE[d.weekday()] not in working_days:
            continue
        if d == today:
            end_of_day = datetime.combine(d, config.afternoonEndTime)
            if now + timedelta(minutes=config.minimumBookingTime) >= end_of_day:
                continue
        result.append(d)
    return result


def get_specializations_brief():
    #Danh sách chuyên khoa (id, tên, mô tả) để đưa vào ngữ cảnh cho AI phân loại.
    return [
        {"id": s.id, "name": s.name, "description": s.description or ""}
        for s in get_all_specializations()
    ]


def get_available_slots_for_doctor_on_date(doctor_id, work_date, slot_minutes=30):
    #lọc theo 1 ngày cụ thể
    #(dùng cho chatbot vì bệnh nhân đã chọn ngày trước khi mô tả triệu chứng).
    blocks = get_work_schedules_for_doctor_on_date(doctor_id, work_date)
    booked_times = get_booked_times_for_doctor_date(doctor_id, work_date)
    slots = []
    for block in blocks:
        if not block.isAvailable:
            continue
        for start_t, end_t in split_time_range(block.startTime, block.endTime, slot_minutes):
            if start_t in booked_times:
                continue
            slots.append({
                "work_schedule_id": block.id,
                "work_date": block.workDate,
                "session": block.session,
                "start": start_t,
                "end": end_t,
            })
    return slots


def get_doctors_with_slots_by_specialization_on_date(
    specialization_id, work_date, slot_minutes=30, doctor_limit=5, slot_limit=8
):
    #tra cứu bác sĩ thuộc chuyên khoa + khung giờ trống trong ngày đã chọn.
    doctors = get_doctors_by_specialization(specialization_id)
    result = []
    for d in doctors:
        slots = get_available_slots_for_doctor_on_date(d.id, work_date, slot_minutes)
        if not slots:
            continue
        result.append({"doctor": d, "slots": slots[:slot_limit]})
    result.sort(key=lambda x: (x["doctor"].averageRating or 0), reverse=True)
    return result[:doctor_limit]


def create_chatbot_session(user, query_text, booked_date, specialization_id=None, ai_requirements=None):
    session = ChatbotSession(
        userId=user.id,
        queryText=query_text,
        bookedDate=booked_date,
        specializationId=specialization_id,
        aiRequirements=ai_requirements,
    )
    db.session.add(session)
    db.session.commit()
    return session


def update_chatbot_session_specialization(session, specialization_id, ai_requirements=None):
    session.specializationId = specialization_id
    if ai_requirements is not None:
        session.aiRequirements = ai_requirements
    db.session.commit()
    return session


def add_chatbot_doctor_suggestion(session_id, doctor_id, available_date, start_time, end_time, reason=None):
    suggestion = ChatbotDoctorSuggestion(
        sessionId=session_id,
        doctorId=doctor_id,
        availableDate=available_date,
        startTime=start_time,
        endTime=end_time,
        reason=reason,
    )
    db.session.add(suggestion)
    db.session.commit()
    return suggestion


def get_chatbot_session_by_id(session_id):
    return ChatbotSession.query.get(session_id)


def get_chatbot_suggestion_by_id(suggestion_id):
    return ChatbotDoctorSuggestion.query.get(suggestion_id)