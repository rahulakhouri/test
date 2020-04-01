from django.shortcuts import render
from datetime import datetime 
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger 
from django.contrib.auth.decorators import login_required, user_passes_test
from leave.models import UserProfile,Employee,Application,ApplicationLog,TransactionLog,Action,EmployeeUpdateLog
from django.shortcuts import redirect
from django.core.exceptions import ObjectDoesNotExist,PermissionDenied
from django.http import HttpResponse,Http404
from django.template import RequestContext, loader
from django import forms
from django.contrib.auth import authenticate,login,logout
from leave.forms import ApplicationForm,EmployeeEditForm,EmployeeNewForm,CancelForm,CreditApplicationForm,SelectEmployeeForm
from django.views.generic import ListView
from django.contrib import messages
from django.core.urlresolvers import reverse
import json
from EmployeeSerializer import EmployeeSerializer
from django.core import serializers
from django.db import IntegrityError, transaction
from django.db.models import Q



# are divided to Depts,Clerk,'Higher'
#'higher' includes Dean,Dr,Registrar Etc
#These functions are used to verify user's groups
def isDept(user):
	return user.groups.filter(name='depts')

def isClerk(user):
	return user.groups.filter(name='clerk')

def isHigher(user):
	return user.groups.filter(name='higher')

def isDataEntry(user):
	return user.groups.filter(name="data_entry")


def getStatus(sort):
	if(sort==None):
		status=0
	elif(sort.lower()=="pending"):
		status=1
	elif(sort.lower()=="processing"):
		status=2
	elif(sort.lower()=="approved"):
		status=3
	elif(sort.lower()=="rejected"):
		status=4
	elif(sort.lower()=="cancelled"):
		status=5
	elif(sort.lower()=="all"):
		status=6
	else:
		status=0
	return status

def isCredit(type):
	if type==None:
		return False
	elif type=="credit":
		return True
	else:
		return False

def getApplicationsList(page,status,year,month,date):
	all_list=Application.objects.all().order_by("-time_generated")
	if 1<= status <=5 :
		all_list=all_list.filter(status=status)

	if status==7:
		all_list=all_list.filter(Q(status=1)|Q(status=2))

	if year:
		all_list=all_list.filter(time_generated__year=year)
	
	if month:
		all_list=all_list.filter(time_generated__month=month)
	if date:
		all_list=all_list.filter(time_generated__day=date)
	paginator = Paginator(all_list, 10)
	
	try:
		applications = paginator.page(page)
	except PageNotAnInteger:
		# If page is not an integer, deliver first page.
		applications = paginator.page(1)
	except EmptyPage:
		# If page is out of range (e.g. 9999), deliver last page of results.
		applications = paginator.page(paginator.num_pages)
	return applications


# Create your views here.
def index(request):

	#Authenticate User
	if(request.method=='POST'):		#
		username = request.POST['username']
		password = request.POST['password']
		user = authenticate(username=username, password=password)
		if user is not None and user.is_active:  
			login(request, user)
			#Login User
		else:
			   return render(request, 'leave/login.html',{'message':"Invalid login !",'username':username})
	   	  	# Return an 'invalid login' error message.

	
	
	if request.user.is_authenticated():
		if request.user.is_staff:
			return redirect('admin:index')

		userprofile=UserProfile.objects.get(user=request.user)
		#User authenticated, Now redirect to corresponding Home pages
		context={
		'user_type':userprofile.user_type,
		}
		
		if isHigher(request.user):

			context['pending_count']=Application.objects.filter(status=1).count()
			context['processing_count']=Application.objects.filter(status=2).count()
			context['actions_count']=Action.objects.filter(status=1).count()
			return render(request,'leave/dr.html',context)
		elif isClerk(request.user):
			context['pending_count']=Application.objects.filter(status=1).count()
			return render(request,'leave/est_office.html',context)
		elif isDept(request.user):
			return render(request,'leave/dept.html',context)
		elif isDataEntry(request.user):
			return render(request,'leave/est_admin.html',context)
		else:
			#If user do not belong to any of three groups, then it should be considered as a staff
			#Redirect this user to Admin page
			return redirect('admin:index')

	else:
		
		#Return a fresh login page
		return render(request, 'leave/login.html',{'message':""})


def logt(request):
	logout(request)
	return redirect('index')
		
@login_required
@user_passes_test(isHigher)
def manage_action(request):
	if request.method=='POST':
		action_id=request.POST.get('action','')
		status=request.POST.get('status','')
		action_id=int(action_id)
		status=int(status)
		to_json = {}
		try:
			action=Action.objects.get(pk=action_id)
		except Action.DoesNotExist:
			messages.error(request,'Some error occured')
			to_json['result']=0
			to_json['message']='Some error occured'
		else:
			if 3 <= status <=4 and action.status==1:
				
				if status==3:
					if action.is_leave:
						entries=TransactionLog.objects.filter(action=action)
						valid=True
						for entry in entries:
							if entry.employee.hp_balance < entry.hp_balance*-1 or entry.employee.earned_balance < entry.earned_change*-1:
								valid=False
								break

						if valid:
							for entry in entries:
								entry.employee.transaction(entry.hp_change,entry.earned_change)
								entry.hp_balance=entry.employee.hp_balance
								entry.earned_balance=entry.employee.earned_balance
								entry.save()
							action.status=status
							action.time_approved=datetime.now()
							action.save()

							messages.success(request,'Action approved')
							
							to_json['result']=1
							to_json['message']='Action approved'
								
						else:
							to_json['result']=0
							to_json['message']="Couldn't approve action, Insufficient leave balance"
							messages.error(request,"Couldn't approve action, Insufficient leave balance")
					else:
						action.status=status
						action.time_approved=datetime.now()
						action.save()
						update_log=action.update_log
						employee=update_log.employee
						employee.name=update_log.new_name
						employee.dept=update_log.new_dept
						employee.email=update_log.new_email
						employee.is_active=update_log.new_is_active
						employee.save()
						messages.success(request,'Action approved, Employee Details Updated')
						to_json['result']=1
						to_json['message']='Action approved, Employee Details Updated'

				elif status==4:
					action.status=status
					action.time_approved=datetime.now()
					action.save()
					messages.success(request,'Action rejected')
					to_json['result']=1
					to_json['message']='Action rejected'


			else:
				to_json['result']=0
				to_json['message']="Some error occured"
				messages.error(request,'Some error occured')

		return HttpResponse(json.dumps(to_json))




@login_required
@user_passes_test(isDataEntry)
def action_history(request,sort):
	status=getStatus(sort)
	if status==0:
		status=6

	userprofile=UserProfile.objects.get(user=request.user)
	page=request.GET.get('page','')
	actions=Action.objects.all().order_by("-time_generated")
	if 1<= status <=4:
		actions=actions.filter(status=status)

	paginator = Paginator(actions,20)
	try:
		actions = paginator.page(page)
	except PageNotAnInteger:
		# If page is not an integer, deliver first page.
		actions = paginator.page(1)
	except EmptyPage:
		# If page is out of range (e.g. 9999), deliver last page of results.
		actions = paginator.page(paginator.num_pages)
	
	context={
	'actions':actions,
	'user_type':userprofile.user_type,
	'status':status,
	}
	return render(request,'leave/action_history.html',context)


@login_required
def print_action(request,id):
	userprofile=UserProfile.objects.get(user=request.user)
	try:
		action=Action.objects.get(pk=id)
	except Action.DoesNotExist:
		raise Http404
	context={
	'user_type':userprofile.user_type,
	'action':action,
	}

	if action.is_leave:
		entries=TransactionLog.objects.filter(action=action)
		page=request.GET.get('page','')
		paginator = Paginator(entries,20)
		try:
			entries = paginator.page(page)
		except PageNotAnInteger:
			# If page is not an integer, deliver first page.
			entries = paginator.page(1)
		except EmptyPage:
		# If page is out of range (e.g. 9999), deliver last page of results.
			entries = paginator.page(paginator.num_pages)
		context['entries']=entries

	
	return render(request,'leave/print_action.html',context)


@login_required
def action(request,id):
	userprofile=UserProfile.objects.get(user=request.user)
	try:
		action=Action.objects.get(pk=id)
	except Action.DoesNotExist:
		raise Http404
	context={
	'user_type':userprofile.user_type,
	'action':action,
	}

	if action.is_leave:
		entries=TransactionLog.objects.filter(action=action)
		page=request.GET.get('page','')
		paginator = Paginator(entries,20)
		try:
			entries = paginator.page(page)
		except PageNotAnInteger:
			# If page is not an integer, deliver first page.
			entries = paginator.page(1)
		except EmptyPage:
		# If page is out of range (e.g. 9999), deliver last page of results.
			entries = paginator.page(paginator.num_pages)
		context['entries']=entries

	
	return render(request,'leave/action.html',context)


@login_required
@user_passes_test(isHigher)
def actions(request,sort):
	status=getStatus(sort);
	if status==0:
		status=1

	userprofile=UserProfile.objects.get(user=request.user)
	actions=Action.objects.filter(status=status)
	page=request.GET.get('page','')
	paginator = Paginator(actions,20)
	try:
		actions = paginator.page(page)
	except PageNotAnInteger:
		# If page is not an integer, deliver first page.
		actions = paginator.page(1)
	except EmptyPage:
		# If page is out of range (e.g. 9999), deliver last page of results.
		actions = paginator.page(paginator.num_pages)
	context={
	'actions':actions,
	'user_type':userprofile.user_type,
	'status':status,
	}
	return render(request,'leave/actions.html',context)


@login_required
@user_passes_test(isDataEntry)
def delete_action(request):
	if request.method=='POST':
		action=Action.objects.get(pk=request.POST.get('id'))
		if action.status==1:
			action.status=0
			action.save()
			messages.success(request, 'Action Deleted.')
		else:
			messages.error(request,'Only Pending Actions can be deleted')
		return redirect(reverse('action',args=(action.pk,)))
	else:
		PermissionDenied


@login_required
@user_passes_test(isDataEntry)
def manage_leave(request):
	if request.method=='POST':
		leave_type=request.POST.get('leave_type','')
		action_type=request.POST.get('action_type','')
		days=request.POST.get('count','')
		note=request.POST.get('note','')
		try :
			leave_type=int(leave_type)
			action_type=int(action_type)
			days=int(days)
		except ValueError:
			messages.error(request,"Invalid Inputs")
			return redirect(reverse('employees'))


		
		if 1<= leave_type <=2 and (action_type==-1 or action_type==1) and days>=0:
			count=0
			employees=request.POST.getlist('check[]')
			action=Action(note=note,)
			action.save()

			for pk in employees:
				try:
					employee=Employee.objects.get(pk=pk)
				except Employee.DoesNotExist:
					pass
				else:
					if action_type==-1 and not employee.isLeaveLeft(days,leave_type):
						pass
					else:
						
						TransactionLog().AdminTransaction(action,employee,leave_type,days,action_type,note)
						count=count+1


			if count:
				messages.success(request,"Leave Credit/Debit of "+str(count)+" employees sent for approval")
				action.count=count
				action.save()
			else:
				messages.error(request,"Error. No employee selected")
				action.delete()
		

		else:
			messages.error(request,"Invalid Action")

		return redirect(reverse('employees'))
	else:
		raise PermissionDenied

@login_required
@user_passes_test(isDept)
def cancel(request,id):
	userprofile=UserProfile.objects.get(user=request.user)
	try:
		application=Application.objects.get(pk=id)
	except Application.DoesNotExist:
		raise Http404

	if application.employee.dept!=userprofile.dept:
		raise PermissionDenied

	if not application.is_new:
		return HttpResponse("Cancel requests can't be cancelled!")
	if application.is_credit:
		return HttpResponse("Credit requests can't be cancelled!")


	if application.status!=3:
		return HttpResponse("This application is now "+application.get_status_display()+
		", Cancellation request can be initiated only for APPROVED applications ")

	if application.original:
		messages.error(request,"There already exists a cancel request for this application ")
		return redirect(reverse('details',args=(application.original.pk,)))

	new_form=CancelForm()
	context={
	'user_type':userprofile.user_type,
	'form':new_form,
	'application':application,

	}

	if request.method=='POST':
		form=CancelForm(request.POST,request.FILES)
		if form.is_valid():
			reason=form.cleaned_data['reason']
			att1=form.cleaned_data['attachment1']
			att2=form.cleaned_data['attachment2']
			att3=form.cleaned_data['attachment3']
			cancel_application=application.CancelRequest(reason,att1,att2,att3)
			activity="Application generated by "+userprofile.get_user_type_display()
			log_entry=ApplicationLog(application=cancel_application,time=datetime.now(),activity=activity)
			log_entry.save()
			messages.success(request,"Cancellation request created")
			return redirect(reverse('details',args=(cancel_application.pk,)));
		else:
			context['form']=form

	return render(request,'leave/cancel.html',context)

@login_required
@user_passes_test(isDept)
def delete_application(request):
	if request.method=='POST':
		userprofile=UserProfile.objects.get(user=request.user)
		application_id=request.POST.get('id')
		application=Application.objects.get(pk=application_id)
		if application.employee.dept==userprofile.dept and application.status==1:

			application.status=0


			#Think , Think , Think :P 
			if not application.is_new:
				application.original.original=None  
				application.original.save()
				# Because now, no Cancel requests going on for that particular application


			application.save()

			activity="Application deleted by "+userprofile.get_user_type_display()
			log_entry=ApplicationLog(application=application,time=datetime.now(),activity=activity)
			log_entry.save()
			messages.success(request, 'Application Deleted.')

		else:
			messages.error(request, 'Some error occured: Could not delete application.')

		return redirect(reverse('details', args=(application.pk,)))
	else:
		raise PermissionDenied

		
@login_required
@user_passes_test(isClerk)
def start_processing(request):
	
	if(request.method=='POST'):
		userprofile=UserProfile.objects.get(user=request.user)
		user_type=userprofile.user_type
		application_id=request.POST.get('id')
		application=Application.objects.get(pk=application_id)
		to_json={}
		notes=request.POST.get('notes',"")
				
		if application.status==1 and isClerk(request.user):
				
			application.status=2
			application.save()
			activity="Processing started "
			log_entry=ApplicationLog(application=application,time=datetime.now(),activity=activity,notes=notes)
			log_entry.save()
			to_json['result']=1
			to_json['message']='Application marked as processing'
			messages.success(request, 'Application marked as processing')
		else:
			to_json['result']=0
			to_json['message']='error'
			messages.error(request,'Error: Could not change status. Try again.')
		return HttpResponse(json.dumps(to_json))
	else:
		raise PermissionDenied

@login_required
def print_application(request,id):
	try:
		application=Application.objects.get(pk=id)
	except Application.DoesNotExist:
		raise Http404
	employee=application.employee
	log=TransactionLog.objects.filter(
	(Q(is_admin=False)|Q(action__status=3)),time__lt=application.time_received,
	employee=employee).order_by("-time")[:5]
	if application.is_credit:
		days_count=application.days						
	else:
		days_count=(application.date_to-application.date_from).days+1

	context={
	'application':application,
	'days_count':days_count,
	'log':log
	}
	return render(request,'leave/print.html',context)




@login_required
@user_passes_test(isHigher)
def complete(request):
	if(request.method=='POST'):
		userprofile=UserProfile.objects.get(user=request.user)
		application_id=request.POST.get('id')
		status=request.POST.get('status')
		status=int(status)
		date_from=request.POST.get('date_from',"")
		date_to=request.POST.get('date_to',"")
		notes=request.POST.get('notes',"")
		application=Application.objects.get(pk=application_id)
		employee=application.employee
		to_json = {}
		valid=True
		if not application.is_credit:
			if not application.is_new:
				date_to=application.new_date_to
				date_from=application.new_date_from
				
			else:

				try:
							
					date_to=datetime.strptime(date_to, "%m/%d/%Y").date()
					date_from=datetime.strptime(date_from, "%m/%d/%Y").date()
					

				except ValueError:
					valid=False
					to_json['message']='Invalid dates entered.'
				else:
					if date_from>date_to or date_to>application.new_date_to or date_from<application.new_date_from:
						valid=False
						to_json['message']='Selected dates out of range. Please select valid dates.'
				if not valid:
					to_json['result']=0
					messages.error(request, to_json['message'])
					return HttpResponse(json.dumps(to_json))
			days=(date_to-date_from).days+1

		else:
			days=application.days
		

		if application.status== 2 and 3 <= status <= 4:
			

			if application.is_credit or (not application.is_new) or status==4 or employee.isLeaveLeft(days,application.leave_type):
				application.status=status
				application.time_approved=datetime.now()
				if status==3 and not application.is_credit:
					if (application.new_date_from!=date_from or application.new_date_to!=date_to):
						if notes and notes!="":
							notes+='\n'
						notes+=userprofile.get_user_type_display()+" updated  date  : "+str(date_from)+" to "+str(date_to)
					application.new_date_from=date_from
					application.new_date_to=date_to
				else:
					if not application.is_new:
						application.original.original=None
						application.original.save()
						#IMPORTANT  Set original to Null in case of rejecting Cancel Application

				application.save()

				if application.status==3: 
					if application.is_credit:
						if application.is_new:
							action_type=1
						else :
							action_type=-1
					else:
						if application.is_new:
							action_type=-1
						else :
							action_type=1


					employee.approveTransaction(days,application.leave_type,action_type)
					TransactionLog().ApplicationTransaction(employee,application)
					#Danger!
				

					

				activity="Application "+application.get_status_display()
				log_entry=ApplicationLog(application=application,time=datetime.now(),activity=activity,notes=notes)
				log_entry.save()
				messages.success(request, 'Application '+application.get_status_display()+' successfully')
				
				to_json['result']=1
				to_json['message']='Application '+application.get_status_display()+' successfully'
    
				
				
			else:
				to_json['result']=0
				to_json['message']="Insufficient number of leaves left!"
				messages.error(request, 'Insufficient number of leaves left!')



		else:
			to_json['result']=0
			to_json['message']='Some error occured. Please try again'
		return HttpResponse(json.dumps(to_json))
	else:
		raise PermissionDenied


@login_required
def details(request,id):
	userprofile=UserProfile.objects.get(user=request.user)
	try:
		application=Application.objects.get(pk=id)
	except Application.DoesNotExist:
		raise Http404
	if isDept(request.user) and application.employee.dept!=userprofile.dept:
		raise PermissionDenied
	if isClerk(request.user) and not application.time_received:
		application.time_received=datetime.now()
		application.save()
		activity="Application Received at Est.Office"
		log_entry=ApplicationLog(application=application,time=datetime.now(),activity=activity)
		log_entry.save()

	application_log=ApplicationLog.objects.filter(application=application).order_by("time")

	approved_days_count=None
	if application.is_credit:
		days_count=application.days	
		approved_days_count=application.days					
	else:
		days_count=(application.date_to-application.date_from).days+1
		approved_days_count=(application.new_date_to-application.new_date_from).days+1

	context= {
	'name':request.user.username,
	'application':application,
	'days_count':days_count,
	'user_type':userprofile.user_type,
	'approved_days_count':approved_days_count,
	'user_display_name':userprofile.get_user_type_display,
	#'dept': userprofile.dept.name,
	'application_log':application_log
	}
	return render(request,'leave/application.html',context)

@login_required
def select_employee(request):
	userprofile=UserProfile.objects.get(user=request.user)
	
	dept=None
	if isDept(request.user):
		dept=userprofile.dept
		
	user_type=userprofile.user_type

	form=SelectEmployeeForm(dept,user_type)
	if request.method=='POST':
		form=SelectEmployeeForm(dept,user_type,request.POST)
		if form.is_valid():
			employee=form.cleaned_data['employee']
			return redirect(reverse('employee',args=(employee.pk,)))
	

	context={
	'form':form,
	'user_type':userprofile.user_type
	}
	return render(request,'leave/select_employee.html',context)



@login_required
def employee(request,id):
	userprofile=UserProfile.objects.get(user=request.user)
	page=request.GET.get('page')
	try:
		employee=Employee.objects.get(pk=id)
	except Employee.DoesNotExist:
		raise Http404
	if isDept(request.user) and employee.dept!=userprofile.dept:
		raise PermissionDenied
	all_list=TransactionLog.objects.filter((Q(is_admin=False)|Q(action__status=3)),employee=employee).order_by("-time")

	paginator = Paginator(all_list, 10)
	
	try:
		transaction_log = paginator.page(page)
	except PageNotAnInteger:
		# If page is not an integer, deliver first page.
		transaction_log = paginator.page(1)
	except EmptyPage:
		# If page is out of range (e.g. 9999), deliver last page of results.
		transaction_log = paginator.page(paginator.num_pages)

	context= {
	'name':request.user.username,
	'employee':employee,
	'user_type':userprofile.user_type,
	'user_display_name':userprofile.get_user_type_display,
	#'dept': userprofile.dept.name,
	'transaction_log': transaction_log
	}

	return render(request,'leave/employee.html',context)

@login_required
@user_passes_test(isDataEntry)
def edit_employee(request,id):
	userprofile=UserProfile.objects.get(user=request.user)
	try:
		employee=Employee.objects.get(pk=id)
	except Employee.DoesNotExist:
		raise Http404

	try:
		action=Action.objects.get(is_leave=False,status=1,update_log__employee=employee)
		messages.success(request, 'An update action is already pending')
		return redirect(reverse('action',args=(action.pk,)))
	except Action.DoesNotExist:
		pass



	form=EmployeeEditForm(initial={'new_name':employee.name,'new_dept':employee.dept
	,'new_email':employee.email,'new_is_active':employee.is_active})
	context={
	'employee':employee,
	'form':form,
	'user_type':userprofile.user_type
	}
	if request.method=='POST':
		form = EmployeeEditForm(request.POST)
		if form.is_valid():
			new_name=form.cleaned_data['new_name']
			new_dept=form.cleaned_data['new_dept']
			new_email=form.cleaned_data['new_email']
			new_is_active=form.cleaned_data['new_is_active']
			note=form.cleaned_data['note']
			if(new_name==employee.name and new_dept==employee.dept and new_email==employee.email and new_is_active==employee.is_active):
		 		messages.error(request,'No details updated')
		 		context['form']=form
			else:
				action=Action(note=note,is_leave=False)
				action.save()
				update=EmployeeUpdateLog(action=action,employee=employee,new_name=new_name,new_dept=new_dept,
			 	new_email=new_email,new_is_active=new_is_active,old_name=employee.name,old_dept=employee.dept,
				old_email=employee.email,old_is_active=employee.is_active)
				update.save()
				messages.success(request, 'Employee details update sent for approval')
				return redirect(reverse('action',args=(action.pk,)))
			
		else:
			messages.error(request,'Please correct incorrect fields')
			context['form']=form
		return render(request,'leave/edit_employee.html',context)
	
	else:	
		return render(request,'leave/edit_employee.html',context)

@login_required
@user_passes_test(isDataEntry)
def new_employee(request):
	userprofile=UserProfile.objects.get(user=request.user)

	context={
	'user_type':userprofile.user_type,
	}
	if request.method=='POST':
		form = EmployeeNewForm(request.POST)
		code=form.data['code']
		
		try:
			employee=Employee.objects.filter(is_active=False).get(code=code)
			messages.success(request, 'Employee code already exists ,Please update details Here')
			return redirect(reverse('edit_employee',args=(employee.pk,)))
		except Employee.DoesNotExist:
			if form.is_valid():
					
				new_employee=form.save()
				note="Adding new employee"
				action=Action(note=note,is_leave=False)
				action.save()
				update=EmployeeUpdateLog(action=action,is_new=True,employee=new_employee,new_name=new_employee.name,				 	new_dept=new_employee.dept,new_email=new_employee.email,new_is_active=True,
				old_name=new_employee.name,old_dept=new_employee.dept,
			 	old_email=new_employee.email,old_is_active=False)
				update.save()
				messages.success(request, 'Request to add new employee sent for approval')
				return redirect(reverse('action',args=(action.pk,)))
			else:
				messages.error(request,'Please correct incorrect fields')
				context['form']=form
		return render(request,'leave/new_employee.html',context)
	
	
	else:	
		context['form']=EmployeeNewForm()
		return render(request,'leave/new_employee.html',context)



@login_required
@user_passes_test(isDataEntry)
def employees(request):
	userprofile=UserProfile.objects.get(user=request.user)
	employees=Employee.objects.filter(is_active=True)
	serializer = EmployeeSerializer()
	serialized_employees = serializer.serialize(employees)
	
	context={
	'employees':serialized_employees,
	'user_type':userprofile.user_type
	}
	
	return render(request,'leave/employees.html',context)


@login_required
@user_passes_test(isDept)
def sent(request,sort,year,month,date):
	userprofile=UserProfile.objects.get(user=request.user)
	status=getStatus(sort)
	page = request.GET.get('page')
	applications=getApplicationsList(page,status,year,month,date)

	context= {
	'name': request.user.username,
	'dept': userprofile.dept.name,
	'applications':applications,
	'status' :status,
	'user_type': userprofile.user_type,
	}

	return render(request,'leave/sent.html',context)


@login_required
@user_passes_test(isDept)
def dept(request):
	userprofile=UserProfile.get(user=request.user)
	context={
	'user_type':userprofile.user_type
	}
	return render(request,'leave/dept.html',context)
	


@login_required	#Require Login
@user_passes_test(isDept) #Restrict access to users from other groups 
def new_application(request,type):

	#Information specific to the user

	userprofile=UserProfile.objects.get(user=request.user)
	
	context= {
	'name': request.user.username,
	'dept': userprofile.dept.name,
	'user_type': userprofile.user_type,
	'is_credit':isCredit(type)
	}


	if(request.method=='POST'):
		if isCredit(type):
			form=CreditApplicationForm(userprofile.dept,request.POST,request.FILES)
		else:
			form = ApplicationForm(userprofile.dept,request.POST,request.FILES)
		if(form.is_valid()):
			new_application=form.save()

			if not isCredit(type):
				new_application.new_date_from=new_application.date_from
				new_application.new_date_to=new_application.date_to
				new_application.save()
			#These three lines shouldn't be here
			
			activity="Application generated by "+userprofile.get_user_type_display()
			log_entry=ApplicationLog(application=new_application,time=datetime.now(),activity=activity)
			log_entry.save()
			messages.success(request, 'Application added successfully')
			return redirect(reverse('details', args=(new_application.pk,)))
		else:
			context['form']=form

			return render(request,'leave/new_application.html',context)


	else:
		if isCredit(type):
			form=CreditApplicationForm(userprofile.dept)
		else:
			form=ApplicationForm(userprofile.dept)
		context['form']=form
		return render(request,'leave/new_application.html',context)




@login_required
def applications(request,sort,year,month,date):
	if isHigher(request.user):
		return higher(request,sort,year,month,date)
	elif isClerk(request.user):
		return clerk(request,sort,year,month,date)
	else:
		raise Http404

@login_required
@user_passes_test(isClerk)
def clerk(request,sort,year,month,date):
	userprofile=request.user.userprofile
	status=getStatus(sort)
	if status==0:
		status=7
	page = request.GET.get('page')
	applications=getApplicationsList(page,status,year,month,date)
	context= {
	'name': request.user.username,
	'applications':applications,
	'status' :status,
	'user_type': userprofile.user_type,
	}

	return render(request,'leave/clerk.html',context)



@login_required
@user_passes_test(isHigher)
def higher(request,sort,year,month,date):

	page=request.GET.get('page')
	userprofile=UserProfile.objects.get(user=request.user)
	status=getStatus(sort)
	if not sort or status==0:
		sort=''

	if status == 0 :
		status = 2

	

	url=reverse('applications', args=(sort,))
	
	if not sort=='':
		url=url+'/'
	
			
		
	
	applications=getApplicationsList(page,status,year,month,date)
	context= {
	'name': request.user.username,
	'applications': applications,
	'status': status,
	'user_type': userprofile.user_type,
	'current_url': url
	}
	return render(request,'leave/higher.html',context)

@login_required
def user_guide(request):
	userprofile=UserProfile.objects.get(user=request.user)
	context={
	'user_type':userprofile.user_type
	}
	return render(request,'leave/user_guide.html',context)
	
