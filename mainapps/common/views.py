from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render,get_list_or_404
from django.views import View
from django.views.generic import CreateView,TemplateView,ListView,DeleteView,UpdateView
from django.urls import reverse
from django.urls import reverse_lazy
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.apps import apps
from django.forms import modelform_factory
from django.contrib import messages


# Create your views here
from cities_light.models import Region, City,SubRegion

from mainapps.common.context_helper import get_context_heper
from mainapps.common.models import Unit
from mainapps.utils.renderings import render_templete
from .intera_messages import InteraMessages
from mainapps.inventory.crud_logic import inventory_creation_logic
from mainapps.inventory.forms import InVentoryForm, InventoryCategoryForm
from mainapps.management.security.encripters import management_dispatch_dispatcher
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.detail import DetailView






class HomEPage(TemplateView):
    # template_name='common/home.html'
    template_name='dashboard/index.html'


"""
#############Most reusable CreateView ever for non-inline_ models#######################################################################################

"""


class GenericDetailView(DetailView):
    template_name = 'common/htmx/detail.html'
    context_object_name = 'item'

    def get_model(self):
        model_name = self.kwargs['model_name']
        app_name = self.kwargs['app_name']
        return apps.get_model(app_name, model_name)

    def get_object(self, queryset=None):
        model = self.get_model()
        return model.objects.get(pk=self.kwargs['pk'])

    def dispatch(self, request, *args, **kwargs):
        management_dispatch_dispatcher(self=self, request=request)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        get_context_heper(self=self, context=context)
        return context


class GenericUpdateView(LoginRequiredMixin, UpdateView):
    template_name = 'common/htmx/create.html' 
    success_url = '/'

    def get_model(self):
        model_name = self.kwargs['model_name']
        app_name = self.kwargs['app_name']
        return apps.get_model(app_name, model_name)

    def get_object(self):
        model = self.get_model()
        return model.objects.get(pk=self.kwargs['pk'])

    def get_form_class(self):
        if self.kwargs['model_name'] == 'inventorycategory':
            return InventoryCategoryForm
        
        elif self.kwargs['model_name'] == 'inventory':
            return InVentoryForm
        
        return modelform_factory(self.get_model(), fields='__all__')

    def dispatch(self, request, *args, **kwargs):
        management_dispatch_dispatcher(self=self, request=request)
        
        if not request.user.has_perm(f'{self.kwargs["app_name"]}.change_{self.kwargs["model_name"]}'): 
            print('no permission')  
            print(self.request.user) 
            if request.htmx:
                return HttpResponse('<div hx-swap-oob="true" id="error-message"><h2>404</h2> <h3>User does not have permission to update this item </h3></div>')
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def get_template(self):
        if self.request.htmx:
            return ['common/htmx/create.html']
        return ['common/create.html']

    def form_valid(self, form):
        try:
            with transaction.atomic():
                if hasattr(self.get_model(), 'profile'):
                    if self.request.user.company:
                        form.instance.profile = self.request.user.company
                    elif self.request.user.profile:
                        form.instance.profile = self.request.user.profile
                if hasattr(self.get_model(), 'updated_by'):
                    form.instance.updated_by = self.request.user
                
                response = super().form_valid(form)
                if self.request.htmx:
                    return HttpResponse('<div hx-swap-oob="true" id="success-message">Item updated successfully</div>')
                return response
        except Exception as error:
            form.add_error(None, error)
            print(error)
            return render_templete(self.request, 'common/htmx/create.html','common/create.html', self.get_context_data())

    def form_invalid(self, form):
        try:
            if self.request.htmx:
                return render(self.request, 'common/htmx/create.html', self.get_context_data())
            return super().form_invalid(form)
        except Exception as error:
            form.add_error("name", error)
            return render(self.request, 'common/htmx/create.html', self.get_context_data())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.get_form()
        get_context_heper(self=self, context=context)
        context['ajax_url'] = f'/update/{self.kwargs["app_name"]}/{self.kwargs["model_name"]}/{self.kwargs["pk"]}/'
        context['get_url'] = f'/list/{self.kwargs["app_name"]}/{self.kwargs["model_name"]}/'
        context['done_url'] = self.success_url
        return context



class GenericCreateView(LoginRequiredMixin,CreateView):
    template_name = 'common/htmx/create.html'
    success_url='/'
    def get_model(self):
        model_name = self.kwargs['model_name']
        app_name = self.kwargs['app_name']
        return apps.get_model(app_name, model_name)

    def get_form_class(self):
        if self.kwargs['model_name'] == 'inventorycategory':
            return InventoryCategoryForm
        
        elif self.kwargs['model_name'] == 'inventory':
            return InVentoryForm
        
        return modelform_factory(self.get_model(), fields='__all__')
        


    def dispatch(self, request, *args, **kwargs):
        management_dispatch_dispatcher(self=self,request=request)
        
        if not request.user.has_perm(f'{self.kwargs['app_name']}.add_{self.kwargs['model_name']}'): 
            print('no permission')  
            print(self.request.user) 
            # print(request.user.user_permissions.objects.all()) 
            if request.htmx:
                return HttpResponse('<div hx-swap-oob= "true"  id="error-message"><h2>404</h2> <h3>User does not have permission to create this item </h3></div>')
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
    def get_template(self):
        return render_templete(self.request, 'common/htmx/create.html','common/create.html', self.get_context_data())

    def form_valid(self, form):
        try:

            with transaction.atomic():
                    
                if hasattr(self.get_model(),'profile'):
                    if self.request.user.company:
                        form.instance.profile= self.request.user.company
                    elif self.request.user.profile:
                        form.instance.profile= self.request.user.profile
                if hasattr(self.get_model(),'created_by'):
                    form.instance.created_by = self.request.user
                
                response = super().form_valid(form)
                if self.request.htmx:

                    return HttpResponse('<div hx-swap-oob= "true" id ="success-message">Item created Successfully</div>')
                return response
        except Exception as error:
            form.add_error(None,error)
            print(error)
            return render(self.request, 'common/htmx/create.html',self.get_context_data())
    def form_invalid(self, form):
        try:

            if self.request.htmx:
                return render(self.request, 'common/htmx/create.html',self.get_context_data())
        
            return super().form_invalid(form)
        except Exception as error:
            form.add_error("name",error)
            return render(self.request, 'common/htmx/create.html',self.get_context_data())

    
    def get_context_data(self, **kwargs ) :
        context= super().get_context_data(**kwargs)
        context['form']=self.get_form()
        get_context_heper(self=self,context=context)
        context['ajax_url'] = f'/add/{self.kwargs['app_name']}/{self.kwargs['model_name']}/' 
        context['get_url'] = f'/list/{self.kwargs['app_name']}/{self.kwargs['model_name']}/' 
        context['done_url'] = self.success_url
        return context







class GenericList(ListView):
    paginate_by = 3
    context_object_name = 'items'
    # template_name='common/htmx/tabula_list.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.request.GET.get('page', 1)
        context['get_url'] = f'/list/{self.kwargs['app_name']}/{self.kwargs['model_name']}/' 
        
        context['page_obj'] = context['paginator'].get_page(page)
        get_context_heper(self=self,context=context)
  
        return context
    def dispatch(self, request, *args, **kwargs):
        print( 'this the request: ',request.htmx)
        # print(self.request)
        management_dispatch_dispatcher(self=self,request=request)
        return super().dispatch(request, *args, **kwargs)
    
    def get_template_names(self):
        if hasattr(self.request, 'htmx') and self.request.htmx:
            return ['common/htmx/tabula_list.html']
        else:
            return ['common/tabula_list.html']

    def get_queryset(self):
        model = self.get_model()
        filter_field = self.request.GET.get('filter_field', None)
        filter_val = self.request.GET.get('filter', None)
        order_val = self.request.GET.get('order_by', None)
        print(filter_val)
        print(order_val)
        
        

        if hasattr(model, 'profile'):
            queryset= model.objects.filter(profile=self.company)
        else:
            queryset=model.objects.all()
            
        if filter_field and filter_val:
            filter_kwargs = {filter_field: filter_val}
            
            try:
                queryset = queryset.filter(**filter_kwargs)
                print(queryset)
            except Exception as e:
                print(f"Error filtering by {filter_field}: {e}")
                return queryset
        if order_val :
            queryset = queryset.order_by(order_val)
        else:
            queryset = queryset
        return queryset

    
    def get_model(self):
        model_name = self.kwargs['model_name']
        app_name = self.kwargs['app_name']
        return apps.get_model(app_name, model_name)
    
    # def render_to_response(self, context, **response_kwargs):
    #     if self.request.method == 'GET':
    #         items = list(context['items'].values())
    #         return JsonResponse({
    #             'items': items,
    #             'pagination': {
    #                 'current_page': context['page_obj'].number,
    #                 'total_pages': context['paginator'].num_pages,
    #                 'has_previous': context['page_obj'].has_previous(),
    #                 'has_next': context['page_obj'].has_next(),
    #             }
    #         })
    #     return super().render_to_response(context, **response_kwargs)


def dynamic_delete(request,app_name,company_id, model_name,pk):

    model=apps.get_model(app_name,model_name)
    obj=model.objects.get(pk=pk)
    if request.method=='POST':
        obj.delete()
        # return HttpResponse()
        return HttpResponse(InteraMessages().success('Item deleted Successfully'))

    del_url=f'/delete/{app_name}/{company_id}/{model_name}/{pk}/'
    context={
        "obj":obj,'del_url':del_url,
        "app_label":app_name,
        "model_label":model_name,
        'pk':pk
    }
    return render(request, 'common/confirm_delete.html',context)

class DynamicDeleteView(DeleteView):
    success_url=None
    template_name='common/confirm_delete.html'

    def get_object(self):
        try:

            model= apps.get_model(self.kwargs['app_name'],self.kwargs['model_name'])
            model_id=self.kwargs['pk']
            obj =get_object_or_404(model,pk=model_id)
        except Exception as error:
            return HttpResponse(f'<h2>Object does not exist</h2> {error}')
        return obj
    def delete(self,request,*args,**kwargs):
        if request.method=='POST':
            obj=self.get_object()
            obj.delete()
            if request.htmx:
                return HttpResponse('<div class="modal-content" id ="success-message">Deleted Successfully</div>')
            # return HttpResponseRedirect(self.success_url)
    def get_context_data(self, **kwargs ) :
        context= super().get_context_data(**kwargs)
        context['obj']= self.get_object()
        context['del_url']=f'/delete/{self.kwargs['app_name']}/{self.kwargs['company_id']}/{self.kwargs['model_name']}/{self.kwargs['pk']}/'
        return context
        
    
    # def dispatch(self, request, *args, **kwargs):
    #     management_dispatch_dispatcher(self=self,request=request)
        
    #     if not request.user.has_perm(f'{kwargs['app_name']}.delete_{kwargs['model_name']}'): 
    #         print('no permission')  
    #         print(self.request.user) 
    #         if request.htmx:
    #             return HttpResponse('<div hx-swap-oob= "true" id="error-message"><h2>404</h2> <h3>User does not have permission to delete this item </h3></div>')
    #         return self.handle_no_permission()
    

"""
##############################################Location deals ######################################################
"""

def get_regions(request):
    country_id = request.GET.get('addresses-0-country')
    regions = Region.objects.filter(country_id=country_id)
    return render(request,'common/options.html',{'items':regions,'placeholder':'region'})

def get_subregions(request):
    region_id = request.GET.get('addresses-0-region')
    # subregions = SubRegion.objects.all()
    subregions = SubRegion.objects.filter(region_id=region_id)
    # return render(request,'common/address/subregions.html',{'subregions':subregions})
    return render(request,'common/options.html',{'items':subregions,'placeholder':'subregion'})

def get_cities(request):
    subregion_id = request.GET.get('addresses-0-subregion')
    cities = City.objects.filter(subregion_id=subregion_id).values('id', 'name')
    return render(request,'common/options.html',{'items':cities,'placeholder':'City'})


"""
####################################################################################################
"""
def add_unit(request):
    form=modelform_factory(Unit,fields='__all__')
    if request.method== 'POST':
        new_form= form(request.POST)
        if new_form.is_valid():
            new_form.save()
            return HttpResponse('<div hx-swap-oob= "true" id ="success-message">Unit added Successfully</div>')
    return render(request,'common/inpage_form.html',{'form':form})
def get_unit(request):
    units=Unit.objects.all()
    return render(request,'common/options.html',{'items':units, 'placehoder':'unit'})


def show_popup(request):
    return render(request,'common/components/popup.html',{'content':'hi'})
