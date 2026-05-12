from sba_app.models import UserProfile, CompanyUser


def user_profile(request):
    if not request.user.is_authenticated:
        return {'user_profile': None, 'active_company': None, 'user_companies': []}

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    memberships = (
        CompanyUser.objects
        .filter(user=request.user)
        .select_related('company')
        .order_by('company__name')
    )
    companies = [m.company for m in memberships]

    active_company = None
    user_role = None
    if profile.active_company_id:
        active_company = next((c for c in companies if c.id == profile.active_company_id), None)
        active_membership = next((m for m in memberships if m.company_id == profile.active_company_id), None)
        if active_membership:
            user_role = active_membership.role
    if not active_company and companies:
        active_company = companies[0]
        profile.active_company = active_company
        profile.save(update_fields=['active_company'])
        if not user_role and memberships:
            user_role = memberships[0].role

    return {
        'user_profile': profile,
        'active_company': active_company,
        'user_companies': companies,
        'user_role': user_role,
    }
