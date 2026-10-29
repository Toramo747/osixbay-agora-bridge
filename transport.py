"""Keep platform and app tokens separate. Never forward either across redirects."""
import os,urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):return None

def headers(application_token=None):
    result={'Content-Type':'application/json'}
    if application_token:result['Authorization']='Bearer '+application_token
    gate=os.environ.get('SITES_ACCESS_TOKEN')
    if gate:result['OAI-Sites-Authorization']='Bearer '+gate
    return result

def open_request(request,timeout=30):
    return urllib.request.build_opener(NoRedirect).open(request,timeout=timeout)
