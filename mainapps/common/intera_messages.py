
from django.http import HttpResponse


class InteraMessages:

    def __init__(self,hx_request=None, hx_trigger='revealed', target=None,) -> None:
        self.hx_request=hx_request
        self.hx_trigger=hx_trigger
        self.target=target

    def warnining(self,message):

        return self.compile_message(message,'warning-message')

    def failed(self,message):

        return self.compile_message(message,'failed-message')

    def success(self,message):

        return self.compile_message(message,'success-message')
    def send_request(self):
        if self.hx_request and self.target:
            hx_request=f"""hx-request='{self.hx_request}' hx-target='#{self.target}' hx-trigger='{self.hx_trigger}' """

            return hx_request
        return
    def compile_message(self,message,status):
        return HttpResponse(
            f"""
            <div class="modal-content in-pd-20 in-mg-y-20 ni-fs-20 in-fw-bld {status} in-btn-primary"  {self.send_request}   >
                {message} 
            </div>
"""
        )                         

    
            