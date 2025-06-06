

def get_context_heper(self,context):
    if hasattr(self.get_model(),'tabular_display'):

        context['table_heads']=self.get_model().tabular_display()
    if hasattr(self.get_model(),'get_verbose_names'):

        context['title']=self.get_model().get_verbose_names('0')
    else:    
        context['title']=self.get_model().__name__


    try:

        context['item_name'] = self.get_model()._meta.verbose_name.title()
    except Exception as error:
        context['item_name'] = self.get_model().__name__

        print(self.get_model().__name__ ,error)    

    try:

        context['plural'] = self.get_model()._meta.verbose_name_plural.title
    except Exception as error:
        print(self.get_model().__name__ ,error)  
    context['model_label']  =self.kwargs['model_name']
    context['app_label']  =self.kwargs['app_name']