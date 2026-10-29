"""Application token only; never forwarded across redirects."""
import os,urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):return None

def headers(application_token=None):
    result={'Content-Type':'application/json'}
    if application_token:result['Authorization']='Bearer '+application_token
    return result

def open_request(request,timeout=30):
    return urllib.request.build_opener(NoRedirect).open(request,timeout=timeout)
